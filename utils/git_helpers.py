import os
import subprocess
from github import Github
from utils.secrets import SecretManager

class AuthException(Exception):
    pass

def get_github_repo(target_repo=None):
    import os
    GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
    repo_name = target_repo if target_repo else GITHUB_REPO
    token = SecretManager.get_github_token()
    if not token or not repo_name:
        raise AuthException("Please add a valid GITHUB_TOKEN to your .env file or provide target_repo")
    from github.GithubException import GithubException
    try:
        gh_client = Github(token)
        return gh_client.get_repo(repo_name)
    except GithubException as e:
        if e.status == 401:
            raise AuthException("Please add a valid GITHUB_TOKEN to your .env file")
        raise e

def create_feature_branch(base_branch="main", new_branch_name=None, target_repo=None):
    if not new_branch_name:
        raise ValueError("new_branch_name is required")
    repo = get_github_repo(target_repo)
    base_ref = repo.get_git_ref(f"heads/{base_branch}")
    repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_ref.object.sha)
    return new_branch_name

def get_branch_diff(base_branch="main", compare_branch=None, target_repo=None):
    if not compare_branch:
         raise ValueError("compare_branch is required")
    repo = get_github_repo(target_repo)
    comparison = repo.compare(base_branch, compare_branch)
    diff = []
    for file in comparison.files:
        filename = file.filename
        if (
            filename.endswith("package-lock.json") or
            filename.endswith("yarn.lock") or
            filename.endswith(".svg") or
            filename.endswith(".png") or
            ".next/" in filename or
            "node_modules/" in filename
        ):
            continue
        diff.append(f"File: {file.filename}\nStatus: {file.status}\nDiff:\n{file.patch}\n")
    return "\n".join(diff)

def merge_and_delete_branch(head_branch, base_branch="main", target_repo=None):
    repo = get_github_repo(target_repo)

    # Check if there is a diff first
    comparison = repo.compare(base_branch, head_branch)
    if comparison.ahead_by == 0:
        return {"status": "success", "message": "Nothing to merge (branches are identical).", "merged": False}

    # Attempt to merge
    try:
        merge_msg = f"Auto-merge {head_branch} into {base_branch}"
        merge_result = repo.merge(base_branch, head_branch, merge_msg)

        # Delete the branch
        ref = repo.get_git_ref(f"heads/{head_branch}")
        ref.delete()
        return {"status": "success", "message": "Branch merged and deleted successfully.", "merged": True, "sha": merge_result.sha}
    except Exception as e:
         return {"status": "error", "message": f"Merge failed: {str(e)}", "merged": False}

def scan_repo_structure(sandbox_path):
    import os

    file_tree = []
    valid_extensions = {'.py', '.ts', '.tsx', '.js'}
    ignored_dirs = {'node_modules', '.git', '__pycache__', '.next', 'build', 'dist', 'out'}

    for root, dirs, files in os.walk(sandbox_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        level = root.replace(sandbox_path, '').count(os.sep)
        indent = ' ' * 4 * (level)
        if root != sandbox_path:
            file_tree.append(f"{indent}{os.path.basename(root)}/")

        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if os.path.splitext(f)[1] in valid_extensions:
                file_tree.append(f"{subindent}{f}")

    if not file_tree:
        return "No relevant files found."

    return "\n".join(file_tree)

import time
import chromadb
import google.generativeai as genai

def _get_embedding_with_retry(text, task_type="retrieval_document", model="models/text-embedding-004", max_retries=3):
    for attempt in range(max_retries):
        try:
            result = genai.embed_content(
                model=model,
                content=text,
                task_type=task_type
            )
            return result['embedding']
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise e

def _chunk_text(text, chunk_size=1000, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start+chunk_size])
        start += chunk_size - overlap
    return chunks

def index_repository(repo_path, prompt):
    import os
    import uuid

    valid_extensions = {'.py', '.ts', '.tsx', '.js'}
    ignored_dirs = {'node_modules', '.git', '__pycache__', '.next', 'build', 'dist', 'out'}

    docs = []
    file_paths = []

    # 1. Chunking
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in valid_extensions:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        rel_path = filepath.replace(repo_path, '').lstrip('/')
                        chunks = _chunk_text(content)
                        for chunk in chunks:
                            docs.append(chunk)
                            file_paths.append(rel_path)
                except Exception:
                    pass

    if not docs:
        return "No relevant source files found."

    # 2. ChromaDB Initialization
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    # Use a dynamic collection name based on repo_path hash or just recreate
    collection_name = "codebase_index"
    try:
        chroma_client.delete_collection(name=collection_name)
    except Exception:
        pass
    collection = chroma_client.create_collection(name=collection_name)

    # 3. Embedding generation and insertion
    # Ensure Gemini API key is configured
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)

    embeddings = []
    ids = []
    metadatas = []

    for i, doc in enumerate(docs):
        # Retrieve embeddings one by one with backoff
        emb = _get_embedding_with_retry(doc)
        embeddings.append(emb)
        ids.append(str(uuid.uuid4()))
        metadatas.append({"filepath": file_paths[i]})

    collection.add(
        embeddings=embeddings,
        documents=docs,
        metadatas=metadatas,
        ids=ids
    )

    # 4. Retrieval
    query_emb = _get_embedding_with_retry(prompt, task_type="retrieval_query")
    top_k = min(5, len(docs))

    results = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k
    )

    radar_report = "--- RADAR REPORT: TOP RELEVANT FILES ---\n\n"
    if results['documents'] and results['documents'][0]:
        for idx, doc in enumerate(results['documents'][0]):
            filepath = results['metadatas'][0][idx]['filepath']
            radar_report += f"File: {filepath}\nSnippet:\n{doc}...\n\n"

    return radar_report
