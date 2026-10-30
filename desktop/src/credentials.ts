import fs from "fs";
import path from "path";
import { agentConfigPath } from "./agent-process";

export type LocalCredentials = {
  username: string;
  password: string;
  naukri_username: string;
  naukri_password: string;
};

const EMPTY: LocalCredentials = {
  username: "",
  password: "",
  naukri_username: "",
  naukri_password: "",
};

function userConfigPath(): string {
  return path.join(path.dirname(agentConfigPath()), "user_config.json");
}

export function readLocalCredentials(): LocalCredentials {
  try {
    const raw = fs.readFileSync(userConfigPath(), "utf8");
    const data = JSON.parse(raw) as { secrets?: Record<string, string> };
    const secrets = data.secrets ?? {};
    return {
      username: String(secrets.username ?? "").trim(),
      password: String(secrets.password ?? "").trim(),
      naukri_username: String(secrets.naukri_username ?? "").trim(),
      naukri_password: String(secrets.naukri_password ?? "").trim(),
    };
  } catch {
    return { ...EMPTY };
  }
}

export function writeLocalCredentials(partial: Partial<LocalCredentials>): LocalCredentials {
  const dir = path.dirname(userConfigPath());
  fs.mkdirSync(dir, { recursive: true });
  let data: { secrets?: Record<string, string>; settings?: Record<string, unknown> } = {};
  try {
    data = JSON.parse(fs.readFileSync(userConfigPath(), "utf8")) as {
      secrets?: Record<string, string>;
      settings?: Record<string, unknown>;
    };
  } catch {
    data = {};
  }
  const secrets = { ...(data.secrets ?? {}) };
  for (const key of ["username", "password", "naukri_username", "naukri_password"] as const) {
    if (key in partial) {
      const value = String(partial[key] ?? "").trim();
      if (value) secrets[key] = value;
      else delete secrets[key];
    }
  }
  data.secrets = secrets;
  const settings = { ...(data.settings ?? {}), safe_mode: true };
  data.settings = settings;
  fs.writeFileSync(userConfigPath(), JSON.stringify(data, null, 2), "utf8");
  return readLocalCredentials();
}
