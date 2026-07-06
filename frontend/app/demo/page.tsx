import Link from "next/link";
import { Nav } from "@/components/landing/Nav";
import { InteractiveDemo } from "@/components/landing/InteractiveDemo";

export const metadata = {
  title: "ClaimSight — Interactive Preview (Sample Data)",
  description:
    "A simulation of ClaimSight's multi-agent pipeline using sample data. Not connected to the real assessment service — start a real claim from the homepage to analyze actual damage photos.",
};

export default function DemoPage() {
  return (
    <main>
      <Nav />
      <InteractiveDemo />
      <div className="border-t border-fog">
        <div className="mx-auto flex max-w-content flex-col items-center gap-4 px-6 py-10 md:flex-row md:justify-between md:px-8">
          <Link href="/" className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-lavender" aria-hidden />
            <span className="text-[15px] font-semibold tracking-heading text-carbon">
              ClaimSight <span className="font-normal text-ash">India</span>
            </span>
          </Link>
          <Link
            href="/"
            className="text-[14px] font-medium text-graphite transition-colors hover:text-carbon"
          >
            ← Back to the story
          </Link>
        </div>
      </div>
    </main>
  );
}
