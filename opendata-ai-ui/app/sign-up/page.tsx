"use client";

import { SignUp } from "@clerk/clerk-react";

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function Page() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      {hasClerk ? (
        <SignUp routing="hash" signInUrl="/sign-in" />
      ) : (
        <p className="text-sm text-slate-500">
          Autenticazione non configurata in questa build.
        </p>
      )}
    </div>
  );
}
