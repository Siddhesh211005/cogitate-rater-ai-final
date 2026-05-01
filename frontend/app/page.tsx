import Link from "next/link";

export default function SplashPage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-background">
      <div className="text-center space-y-4 mb-12">
        <h1 className="text-5xl font-bold tracking-tight">Cogitate</h1>
        <p className="text-muted-foreground text-lg">
          Unified Insurance Rating Engine
        </p>
      </div>

      <div className="flex gap-6">
        <Link
          href="/admin"
          className="flex flex-col items-center justify-center w-52 h-36 rounded-2xl border border-border bg-card hover:bg-accent transition-colors shadow-sm"
        >
          <span className="text-3xl mb-2">🛠️</span>
          <span className="text-lg font-semibold">Admin Portal</span>
          <span className="text-sm text-muted-foreground mt-1">
            Manage raters
          </span>
        </Link>

        <Link
          href="/client"
          className="flex flex-col items-center justify-center w-52 h-36 rounded-2xl border border-border bg-card hover:bg-accent transition-colors shadow-sm"
        >
          <span className="text-3xl mb-2">📋</span>
          <span className="text-lg font-semibold">Client Panel</span>
          <span className="text-sm text-muted-foreground mt-1">
            Calculate premiums
          </span>
        </Link>
      </div>
    </main>
  );
}