"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { CalendarIcon, Loader2, LogOut } from "lucide-react";
import { format } from "date-fns";

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [startDate, setStartDate] = useState<Date>();
  const [startTime, setStartTime] = useState("00:00");
  const [category, setCategory] = useState("retreat");
  const [customKeywords, setCustomKeywords] = useState("");
  const [venmoSelected, setVenmoSelected] = useState(true);
  const [zelleSelected, setZelleSelected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Check for saved credentials on mount
  useEffect(() => {
    const savedEmail = localStorage.getItem("gmail_email");
    const savedPassword = localStorage.getItem("gmail_password");

    if (!savedEmail || !savedPassword) {
      // Redirect to login if not logged in
      router.push("/login");
    } else {
      // Load saved credentials
      setEmail(savedEmail);
      setPassword(savedPassword);
      setIsCheckingAuth(false);
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("gmail_email");
    localStorage.removeItem("gmail_password");
    router.push("/login");
  };

  // Show nothing while checking auth
  if (isCheckingAuth) {
    return null;
  }

  const handleRun = async () => {
    if (!email || !password || !startDate) {
      alert("Please fill in all required fields");
      return;
    }

    if (!venmoSelected && !zelleSelected) {
      alert("Please select at least one payment source");
      return;
    }

    setIsLoading(true);

    // Determine source based on selections
    let source = "venmo";
    if (venmoSelected && zelleSelected) {
      source = "both";
    } else if (zelleSelected) {
      source = "zelle";
    }

    const data = {
      email,
      password,
      startDate: startDate.toISOString().split('T')[0], // Format as YYYY-MM-DD
      startTime,
      category,
      customKeywords: category === "other" ? customKeywords : null,
      source,
    };

    try {
      const response = await fetch("http://localhost:8000/api/scraper/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log("Scraper response:", result);
      
      let sourceLabel = "";
      if (venmoSelected && zelleSelected) {
        sourceLabel = "Venmo & Zelle";
      } else if (venmoSelected) {
        sourceLabel = "Venmo";
      } else {
        sourceLabel = "Zelle";
      }
      
      const message = `Found ${result.data.new_count} new ${sourceLabel} payment(s)\n` +
        `Total Amount: $${result.data.total_amount.toFixed(2)}`;
      
      alert(message);
    } catch (error) {
      console.error("Error calling scraper:", error);
      alert("Error running scraper. Make sure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>AggieWorks Member Payment Tracker</CardTitle>
              <CardDescription>
                Logged in as: {email}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="cursor-pointer"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Payment Source Selection */}
          <div className="space-y-3">
            <Label>Payment Sources</Label>
            <div className="space-y-2">
              <div className="flex items-center space-x-2 cursor-pointer">
                <Checkbox
                  id="venmo"
                  checked={venmoSelected}
                  onCheckedChange={(checked: boolean) => setVenmoSelected(checked)}
                  className="cursor-pointer"
                />
                <Label htmlFor="venmo" className="font-normal cursor-pointer">
                  Venmo
                </Label>
              </div>
              <div className="flex items-center space-x-2 cursor-pointer">
                <Checkbox
                  id="zelle"
                  checked={zelleSelected}
                  onCheckedChange={(checked: boolean) => setZelleSelected(checked)}
                  className="cursor-pointer"
                />
                <Label htmlFor="zelle" className="font-normal cursor-pointer">
                  Zelle
                </Label>
              </div>
            </div>
          </div>

          {/* Category Selection */}
          <div className="space-y-3">
            <Label>Category</Label>
            <RadioGroup value={category} onValueChange={setCategory}>
              <div className="flex items-center space-x-2 cursor-pointer">
                <RadioGroupItem value="retreat" id="retreat" className="cursor-pointer" />
                <Label htmlFor="retreat" className="font-normal cursor-pointer">
                  Retreat
                </Label>
              </div>
              <div className="flex items-center space-x-2 cursor-pointer">
                <RadioGroupItem value="dues" id="dues" className="cursor-pointer" />
                <Label htmlFor="dues" className="font-normal cursor-pointer">
                  Dues
                </Label>
              </div>
              <div className="flex items-center space-x-2 cursor-pointer">
                <RadioGroupItem value="other" id="other" className="cursor-pointer" />
                <Label htmlFor="other" className="font-normal cursor-pointer">
                  Other (custom keywords)
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Custom Keywords */}
          {category === "other" && (
            <div className="space-y-2">
              <Label htmlFor="keywords">Custom Keywords</Label>
              <Textarea
                id="keywords"
                placeholder="Enter keywords separated by commas (e.g., donation, fundraiser, event)"
                value={customKeywords}
                onChange={(e) => setCustomKeywords(e.target.value)}
                rows={3}
              />
            </div>
          )}

          {/* Start Date & Time */}
          <div className="space-y-2">
            <Label>Start Date & Time</Label>
            <div className="flex gap-2">
              <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className="flex-1 justify-start text-left font-normal cursor-pointer"
                >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {startDate ? format(startDate, "PPP") : "Pick a date"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0">
                  <Calendar
                    mode="single"
                    selected={startDate}
                    onSelect={setStartDate}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
              <Input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="w-32 cursor-pointer [&::-webkit-calendar-picker-indicator]:cursor-pointer"
              />
            </div>
          </div>

          {/* Run Button */}
          <Button 
            onClick={handleRun} 
            className="w-full cursor-pointer" 
            size="lg"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Scraping emails...
              </>
            ) : (
              "Run Scraper"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
