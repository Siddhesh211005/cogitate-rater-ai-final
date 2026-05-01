"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface Rater {
  id: string;
  slug: string;
  name: string;
  rater_type: string;
}

export default function ClientPage() {
  const [raters, setRaters] = useState<Rater[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/raters/")
      .then((r) => r.json())
      .then((data) => setRaters(data.raters ?? []))
      .catch(() => setError("Failed to load raters."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Select a Rater</h1>
            <p className="text-muted-foreground mt-1">
              Choose a product to calculate a premium
            </p>
          </div>
          <Link href="/">
            <Button variant="outline">← Home</Button>
          </Link>
        </div>

        {error && (
          <p className="text-destructive mb-4">{error}</p>
        )}

        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-2xl" />
            ))}
          </div>
        )}

        {!loading && raters.length === 0 && !error && (
          <div className="text-center py-24 text-muted-foreground">
            <p className="text-lg">No raters available yet.</p>
            <p className="text-sm mt-1">Ask your admin to upload a rater.</p>
          </div>
        )}

        {!loading && raters.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {raters.map((rater) => (
              <Link key={rater.id} href={`/client/${rater.slug}`}>
                <Card className="hover:shadow-md hover:border-primary/50 transition-all cursor-pointer h-full">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base">{rater.name}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground capitalize">
                      {rater.rater_type}
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}