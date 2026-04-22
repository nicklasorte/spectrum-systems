/// <reference types="next" />
/// <reference types="next/image-types/global" />

declare namespace NodeJS {
  interface ProcessEnv {
    readonly NEXT_PUBLIC_ARTIFACT_API_URL?: string;
    readonly NEXT_PUBLIC_WS_URL?: string;
    readonly ARTIFACT_API_URL?: string;
    readonly WS_URL?: string;
  }
}
