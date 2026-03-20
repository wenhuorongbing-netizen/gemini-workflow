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

def index_repository(repo_path, prompt):
    import os
    import time
    import chromadb
    import google.generativeai as genai

    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)

    def _embed_with_retry(content):
        # Retry with exponential backoff and sleep (Synchronous to avoid thread/event-loop collisions)
        for attempt in range(5):
            try:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=content
                )
                return result['embedding']
            except Exception as e:
                if attempt == 4:
                    raise e
                time.sleep(2 ** attempt)

    client = chromadb.PersistentClient(path="./chroma_db")

    collection_name = "codebase_" + os.path.basename(repo_path.rstrip('/'))
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass
    collection = client.create_collection(name=collection_name)

    docs = []
    file_paths = []

    # Chunking limits
    CHUNK_SIZE = 1000

    valid_extensions = {'.py', '.ts', '.tsx', '.js'}
    ignored_dirs = {'node_modules', '.git', '__pycache__', '.next', 'build', 'dist', 'out'}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in valid_extensions:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                        # Chunking
                        for i in range(0, len(content), CHUNK_SIZE):
                            chunk = content[i:i+CHUNK_SIZE]
                            docs.append(chunk)
                            file_paths.append(filepath.replace(repo_path, '').lstrip('/'))
                except Exception:
                    pass

    if not docs:
        return "No relevant source files found."

    try:
        embeddings = []
        for doc in docs:
            emb = _embed_with_retry(doc)
            embeddings.append(emb)

        prompt_embedding = _embed_with_retry(prompt)
    except Exception as e:
        return f"--- RADAR REPORT ERROR ---\nCould not generate embeddings: {e}"

    # Upsert into ChromaDB
    ids = [str(i) for i in range(len(docs))]
    metadatas = [{"filepath": fp} for fp in file_paths]

    collection.add(
        documents=docs,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

    # Query
    top_n = min(5, len(docs))
    results = collection.query(
        query_embeddings=[prompt_embedding],
        n_results=top_n
    )

    radar_report = "--- RADAR REPORT: TOP RELEVANT FILES ---\n\n"
    if results['documents'] and results['documents'][0]:
        top_docs = results['documents'][0]
        top_metadatas = results['metadatas'][0]

        for i, doc in enumerate(top_docs):
            filepath = top_metadatas[i]['filepath']
            radar_report += f"File: {filepath}\nSnippet (first 500 chars):\n{doc[:500]}...\n\n"

    return radar_report
