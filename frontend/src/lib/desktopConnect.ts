import { desktopAgent, hasDesktopAgent, isDesktopAutomationHost } from "./desktop";
import { automation } from "../services/endpoints";

/** Link this Desktop install to the signed-in account without leaving Automation. */
export async function linkDesktopSilently(): Promise<{ name: string }> {
  const agent = desktopAgent();
  if (!agent?.beginConnect || !agent.completeConnect) {
    throw new Error("ApplyXAI Desktop agent API is unavailable.");
  }
  const begun = await agent.beginConnect();
  await automation.approveConnect(begun.session_id);
  return agent.completeConnect(begun.session_id, begun.secret);
}

export async function reconcileDesktopLink(serverHasDevice: boolean): Promise<{ name: string } | null> {
  if (!isDesktopAutomationHost()) return null;
  const agent = desktopAgent();
  if (!hasDesktopAgent() || !agent?.beginConnect) return null;

  if (serverHasDevice) {
    const valid = agent.validateToken ? await agent.validateToken() : true;
    if (valid) return null;
  }

  if (agent.disconnect) {
    const status = await agent.status();
    if (status.connected) await agent.disconnect();
  }

  return linkDesktopSilently();
}
