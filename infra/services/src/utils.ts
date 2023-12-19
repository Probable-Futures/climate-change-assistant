import * as pulumi from "@pulumi/pulumi";
import { Config as PulumiConfig } from "@pulumi/pulumi/config";
import * as aws from "@pulumi/aws";

export function getRegistryInfo(repo: aws.ecr.Repository) {
  return repo.registryId.apply(async (registryId) => {
    if (!registryId) {
      throw new Error("Expected registry ID to be defined");
    }
    const credentials = await aws.ecr.getCredentials({ registryId });
    const decodedCredentials = Buffer.from(
      credentials.authorizationToken,
      "base64"
    ).toString();
    const [username, password] = decodedCredentials.split(":");
    if (!password || !username) {
      throw new Error("Invalid credentials");
    }
    return {
      server: credentials.proxyEndpoint,
      username: username,
      password: password,
    };
  });
}

enum RequiredTagKeys {
  Name = "Name",
  Environment = "Environment",
  Service = "Service",
  PulumiProject = "PulumiProject",
}

type RequiredTags = {
  [requiredTag in `${RequiredTagKeys}`]: string;
};

type Tags = RequiredTags & aws.Tags;

type CreateTagsArgs = {
  name: string;
  service: string;
  override?: Partial<Tags>;
};

export interface BaseConfig {
  pulumiConfig: PulumiConfig;
  projectName: string;
  stackName: string;
  createTags(args: CreateTagsArgs): Tags;
}

export const createBaseConfig = ({
  pulumiConfig = new PulumiConfig(),
  projectName = pulumi.getProject(),
  stackName = pulumi.getStack(),
}: Partial<BaseConfig> = {}): BaseConfig => ({
  pulumiConfig,
  projectName,
  stackName,
  createTags: ({ name, service, override }) => ({
    [RequiredTagKeys.Name]: name,
    [RequiredTagKeys.Service]: service,
    [RequiredTagKeys.Environment]: stackName,
    [RequiredTagKeys.PulumiProject]: projectName,
    ...(override ?? ({} as aws.Tags)),
  }),
});
