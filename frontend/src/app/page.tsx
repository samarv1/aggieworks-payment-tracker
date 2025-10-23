"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { CalendarIcon } from "lucide-react";
import { format } from "date-fns";

export default function Home() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [startDate, setStartDate] = useState<Date>();
  const [startTime, setStartTime] = useState("00:00");
  const [category, setCategory] = useState("retreat");
  const [customKeywords, setCustomKeywords] = useState("");

  const handleRun = async () => {
    if (!email || !password || !startDate) {
      alert("Please fill in all required fields");
      return;
    }

    const data = {
      email,
      password,
      startDate: startDate.toISOString().split('T')[0], // Format as YYYY-MM-DD
      startTime,
      category,
      customKeywords: category === "other" ? customKeywords : null,
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
      
      alert(`Found ${result.data.new_count} new payment(s). See details in venmo_payments.csv.`);
    } catch (error) {
      console.error("Error calling scraper:", error);
      alert("Error running scraper. Make sure the backend is running.");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>AggieWorks Member Payment Tracker</CardTitle>
          <CardDescription>
            Configure your scraper settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Gmail Information */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="your.email@gmail.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Email Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your email password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {/* Start Date & Time */}
          <div className="space-y-2">
            <Label>Start Date & Time</Label>
            <div className="flex gap-2">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="flex-1 justify-start text-left font-normal"
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
                className="w-32"
              />
            </div>
          </div>

          {/* Category Selection */}
          <div className="space-y-3">
            <Label>Category</Label>
            <RadioGroup value={category} onValueChange={setCategory}>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="retreat" id="retreat" />
                <Label htmlFor="retreat" className="font-normal cursor-pointer">
                  Retreat
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="dues" id="dues" />
                <Label htmlFor="dues" className="font-normal cursor-pointer">
                  Dues
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="other" id="other" />
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

          {/* Run Button */}
          <Button onClick={handleRun} className="w-full" size="lg">
            Run Scraper
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
