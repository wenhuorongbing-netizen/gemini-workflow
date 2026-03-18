export type ActionPlan = {
  action: "click" | "type" | "scroll";
  selector: string;
  value?: string;
  reasoning: string;
};

export interface IAgentProvider {
  analyzeDom(minifiedDom: string, objective: string): Promise<ActionPlan>;
}
