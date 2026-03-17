import os
import google.generativeai as genai

class PMAgent:
    def __init__(self, model_type: str):
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise Exception("GEMINI_API_KEY is not set.")
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro') if model_type == "Pro" else genai.GenerativeModel('gemini-1.5-flash')

    def generate_initial_spec(self, initial_prompt: str, radar_report: str, kb_content: str, corporate_memory: str = "", attachments: list = None):
        """Analyzes requirements and generates the initial technical spec."""
        if attachments and len(attachments) > 0:
            system_prompt = "You are an Expert UI/UX Product Manager. The user has provided a screenshot of a requested UI. Analyze the image and generate a flawless, component-by-step Technical Specification for our developer to build this in Next.js and Tailwind CSS. Detail the colors, layout constraints, and interactions."
        else:
            system_prompt = "You are the Lead Architect for the Auto-DevHouse. Analyze the user request, codebase layout (Radar Report), and any Knowledge Base content. Produce a highly structured Technical Specification and Step-by-Step Implementation Plan for the Developer agent. DO NOT WRITE CODE. Outline exactly what files to edit and how."

        if corporate_memory:
            system_prompt += f"\n\n[COMPANY STANDARDS & PAST MISTAKES TO AVOID]\n{corporate_memory}"

        full_prompt = f"{system_prompt}\n\nUser Request: {initial_prompt}\n\nRadar Report:\n{radar_report}\n\nKnowledge Base:\n{kb_content}"

        content_payload = [full_prompt]
        if attachments:
            import base64
            for att in attachments:
                if att.startswith("data:image"):
                    # Extract the base64 part
                    base64_data = att.split(",")[1]
                    mime_type = att.split(";")[0].split(":")[1]
                    image_bytes = base64.b64decode(base64_data)
                    content_payload.append({
                        "mime_type": mime_type,
                        "data": image_bytes
                    })
                else:
                    # Try raw base64 decode
                    try:
                        image_bytes = base64.b64decode(att)
                        content_payload.append({
                            "mime_type": "image/png", # Default guess
                            "data": image_bytes
                        })
                    except Exception as e:
                        pass # Ignore invalid base64 string

        response = self.model.generate_content(content_payload)

        tokens_burned = 0
        if hasattr(response, 'usage_metadata'):
            tokens_burned = response.usage_metadata.total_token_count

        return response.text, tokens_burned

    def review_diff(self, diff: str, accumulated_context: str):
        """Reviews the generated code diff for correctness and regressions."""
        review_prompt = f"You are the Lead Technical PM. Review this code diff. If the code looks perfect and meets the goal without regressions, output exactly 'LGTM'. Otherwise, provide specific feedback to the developer on what to fix. Diff:\n{diff}\n\nAccumulated Context:\n{accumulated_context}"
        response = self.model.generate_content(review_prompt)

        tokens_burned = 0
        if hasattr(response, 'usage_metadata'):
            tokens_burned = response.usage_metadata.total_token_count

        return response.text, tokens_burned

    def get_model(self):
        """Returns the configured model instance for other agents to share."""
        return self.model
