import os
import google.generativeai as genai

class PMAgent:
    def __init__(self, target_repo_path: str, run_id: str, model_type: str = 'Pro'):
        self.target_repo_path = target_repo_path
        self.run_id = run_id

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise Exception("GEMINI_API_KEY is not set.")

        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro') if model_type == "Pro" else genai.GenerativeModel('gemini-1.5-flash')

    def generate_spec_from_image(self, image_path: str, user_prompt: str) -> str:
        """
        Reads the physical image bytes from the local disk, sends to Gemini 1.5 Pro,
        and returns a step-by-step Technical Specification.
        """
        content_payload = []
        system_prompt = (
            "You are an Expert UI/UX Product Manager. The user has provided a screenshot "
            "of a requested UI. Analyze the image and generate a flawless, component-by-step "
            "Technical Specification for our developer to build this in Next.js and Tailwind CSS. "
            "Detail the colors, layout constraints, and interactions."
        )

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            mime_type = "image/png"
            if image_path.lower().endswith(".jpg") or image_path.lower().endswith(".jpeg"):
                mime_type = "image/jpeg"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"

            content_payload.append({
                "mime_type": mime_type,
                "data": image_bytes
            })
        except Exception as e:
            print(f"[PMAgent] Failed to read image file at {image_path}: {e}")

        full_prompt = f"{system_prompt}\n\nUser Request: {user_prompt}"
        content_payload.append(full_prompt)

        response = self.model.generate_content(content_payload)
        return response.text

    def generate_tech_spec(self, prompt: str, image_url: str = None) -> str:
        """
        Generates a highly detailed Technical Specification string.
        Uses Multi-Modal vision capabilities if an image_url is provided.
        """
        if image_url and image_url.startswith("/uploads/"):
            physical_path = os.path.join(os.getcwd(), "public", image_url.lstrip("/"))
            return self.generate_spec_from_image(physical_path, prompt)

        content_payload = []
        system_prompt = (
            "You are the Lead Architect for the Auto-DevHouse. Analyze the user request "
            "and produce a highly structured Technical Specification and Step-by-Step Implementation "
            "Plan for the Developer agent. DO NOT WRITE CODE. Outline exactly what files to edit and how."
        )

        # Append the text prompt
        full_prompt = f"{system_prompt}\n\nUser Request: {prompt}"
        content_payload.append(full_prompt)

        # Call the Gemini model
        response = self.model.generate_content(content_payload)

        return response.text

    # Backwards compatibility for existing orchestration engine hooks in app.py
    def generate_initial_spec(self, initial_prompt: str, radar_report: str, kb_content: str, corporate_memory: str = "", attachments: list = None):
        """Legacy compatibility wrapper for older run_devhouse_autopilot orchestration."""
        image_url = None
        if attachments and len(attachments) > 0:
            for att in attachments:
                if att.startswith("/uploads/"):
                    image_url = att
                    break

        # Combine the old specific prompt parts to feed into the new streamlined prompt method
        combined_prompt = f"{initial_prompt}\n\nRadar Report:\n{radar_report}\n\nKnowledge Base:\n{kb_content}"
        if corporate_memory:
            combined_prompt = f"[COMPANY STANDARDS & PAST MISTAKES TO AVOID]\n{corporate_memory}\n\n{combined_prompt}"

        spec_text = self.generate_tech_spec(combined_prompt, image_url=image_url)

        # Mock usage since generate_tech_spec signature is fixed to return just a string
        tokens_burned = len(spec_text) // 4
        usage = {'prompt_token_count': len(combined_prompt) // 4, 'candidates_token_count': tokens_burned}

        return spec_text, tokens_burned, usage

    def review_diff(self, diff: str, accumulated_context: str):
        """Reviews the generated code diff for correctness and regressions."""
        review_prompt = f"You are the Lead Technical PM. Review this code diff. If the code looks perfect and meets the goal without regressions, output exactly 'LGTM'. Otherwise, provide specific feedback to the developer on what to fix. Diff:\n{diff}\n\nAccumulated Context:\n{accumulated_context}"
        response = self.model.generate_content(review_prompt)

        tokens_burned = 0
        usage = {}
        if hasattr(response, 'usage_metadata'):
            tokens_burned = response.usage_metadata.total_token_count
            usage = {
                'prompt_token_count': response.usage_metadata.prompt_token_count,
                'candidates_token_count': response.usage_metadata.candidates_token_count
            }

        return response.text, tokens_burned, usage

    def get_model(self):
        return self.model
