import { Nav } from "@/components/landing/Nav";
import { Hero } from "@/components/landing/Hero";
import { Problem } from "@/components/landing/Problem";
import { Workflow } from "@/components/landing/Workflow";
import { AgentSystem } from "@/components/landing/AgentSystem";
import { InteractiveDemo } from "@/components/landing/InteractiveDemo";
import { Metrics } from "@/components/landing/Metrics";
import { Footer } from "@/components/landing/Footer";

export default function HomePage() {
  return (
    <main>
      <Nav />
      <Hero />
      <Problem />
      <Workflow />
      <AgentSystem />
      <InteractiveDemo />
      <Metrics />
      <Footer />
    </main>
  );
}
