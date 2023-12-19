import * as auth0 from "@pulumi/auth0";

import { config } from "./config";

const assistantAuth = new auth0.Client("Assistant", {
  appType: "spa",
  description: "Probable Futures Assistant",
  jwtConfiguration: {
    alg: "RS256",
    lifetimeInSeconds: 36000, // 10 hours
  },
  refreshToken: {
    expirationType: "expiring",
    rotationType: "rotating",
    idleTokenLifetime: 1296000, // 15 days
  },
  oidcConformant: true,
  grantTypes: ["authorization_code", "refresh_token"],
  allowedLogoutUrls: [
    "https://assistant.probablefutures.org",
    "https://dev-assistant.probablefutures.org",
  ],
  callbacks: [
    "https://assistant.probablefutures.org",
    "https://dev-assistant.probablefutures.org",
  ],
  webOrigins: [
    "https://assistant.probablefutures.org/",
    "https://dev-assistant.probablefutures.org/",
  ],
  name: "Probable Futures Assistant",
  logoUri:
    "https://user-images.githubusercontent.com/894075/101797194-be4c8e80-3ad7-11eb-86c8-82516c0a96f0.png",
  tokenEndpointAuthMethod: "none",
});

new auth0.ConnectionClient("google-conn-assistant-client-association", {
  connectionId: config.auth0.googleConnectionId,
  clientId: assistantAuth.clientId,
});

const assistantUserDb = new auth0.Connection("assitant-user-db", {
  options: {
    disableSignup: true,
  },
  strategy: "auth0",
});

new auth0.ConnectionClient("useDb-conn-assistant-client-association", {
  connectionId: assistantUserDb.id,
  clientId: assistantAuth.clientId,
});

export const assistantAuthClientId = assistantAuth.clientId;
