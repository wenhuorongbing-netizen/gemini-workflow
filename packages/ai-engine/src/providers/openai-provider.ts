import { OpenAI } from "openai";
import { ActionPlan, IAgentProvider } from "../types";

export class OpenAIProvider implements IAgentProvider {
  private client: OpenAI;
  private model: string;

  constructor(apiKey: string, model: string = "gpt-4-1106-preview") {
    this.client = new OpenAI({ apiKey });
    this.model = model;
  }

  async analyzeDom(minifiedDom: string, objective: string): Promise<ActionPlan> {
    const systemPrompt = `
You are an advanced autonomous web agent.
You are given a minified DOM representing the current state of a web page and an objective.
Analyze the DOM and determine the best action to take to achieve the objective.
You MUST respond with a JSON object strictly following this format:
{
  "action": "click" | "type" | "scroll",
  "selector": "CSS selector or XPath to interact with",
  "value": "Optional text to type if action is 'type'",
  "reasoning": "A brief explanation of why you chose this action based on the DOM"
}
`;

    const response = await this.client.chat.completions.create({
      model: this.model,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: `Objective: ${objective}\n\nDOM:\n${minifiedDom}` }
      ],
      temperature: 0
    });

    const content = response.choices[0]?.message?.content;
    if (!content) {
      throw new Error("No response content from OpenAI");
    }

    try {
      const parsed = JSON.parse(content) as ActionPlan;
      return parsed;
    } catch (e) {
      throw new Error(`Failed to parse OpenAI response as ActionPlan: ${content}`);
    }
  }
}
