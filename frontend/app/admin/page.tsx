"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface Rater {
  id: string;
  slug: string;
  name: string;
  engine: "excel" | "schema";
  rater_type: string;
  meta: { uploadedAt?: string };
}

export default function AdminDashboard() {
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
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Admin Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Manage uploaded raters
            </p>
          </div>
          <div className="flex gap-3">
            <Link href="/">
              <Button variant="outline">← Home</Button>
            </Link>
            <Link href="/admin/upload">
              <Button>+ Upload Rater</Button>
            </Link>
          </div>
        </div>

        {/* States */}
        {error && (
          <p className="text-destructive mb-4">{error}</p>
        )}

        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-2xl" />
            ))}
          </div>
        )}

        {!loading && raters.length === 0 && !error && (
          <div className="text-center py-24 text-muted-foreground">
            <p className="text-lg">No raters uploaded yet.</p>
            <Link href="/admin/upload">
              <Button className="mt-4">Upload your first rater</Button>
            </Link>
          </div>
        )}

        {/* Rater Cards */}
        {!loading && raters.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {raters.map((rater) => (
              <Card key={rater.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <CardTitle className="text-base leading-snug">
                      {rater.name}
                    </CardTitle>
                    <Badge
                      variant={rater.engine === "excel" ? "default" : "secondary"}
                      className="ml-2 shrink-0 text-xs"
                    >
                      {rater.engine === "excel" ? "Excel" : "Schema"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground capitalize mb-4">
                    {rater.rater_type}
                  </p>
                  {rater.meta?.uploadedAt && (
                    <p className="text-xs text-muted-foreground mb-4">
                      Uploaded{" "}
                      {new Date(rater.meta.uploadedAt).toLocaleDateString()}
                    </p>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      if (confirm(`Delete "${rater.name}"?`)) {
                        fetch(`/api/raters/${rater.id}`, { method: "DELETE" })
                          .then(() =>
                            setRaters((prev) =>
                              prev.filter((r) => r.id !== rater.id)
                            )
                          );
                      }
                    }}
                  >
                    Delete
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}