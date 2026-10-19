"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const router = useRouter();

  useEffect(() => {
    // Remove credentials saved by older versions of the app.
    localStorage.removeItem("gmail_password");
  }, []);

  const handleSelectAccount = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    localStorage.setItem("gmail_email", email.trim().toLowerCase());
    router.push("/");
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>AggieWorks Payment Tracker</CardTitle>
          <CardDescription>
            Choose the Gmail account to search. When you first run the scraper,
            Google will open to authorize read-only email access.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSelectAccount} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="your.email@gmail.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <Button
              type="submit"
              className="w-full cursor-pointer"
              size="lg"
            >
              Continue
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

