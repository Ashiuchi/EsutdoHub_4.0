export {};

declare global {
  interface UserPublicMetadata {
    role?: "admin" | "premium" | "free";
  }

  interface UserUnsafeMetadata {
    bannerUrl?: string;
  }

  // Available in sessionClaims when Clerk JWT template includes publicMetadata
  interface CustomJwtSessionClaims {
    metadata?: {
      role?: "admin" | "premium" | "free";
    };
  }
}
