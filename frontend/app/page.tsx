import { Nav } from "@/components/landing/Nav";
import { Hero } from "@/components/landing/Hero";
import { Problem } from "@/components/landing/Problem";
import { Workflow } from "@/components/landing/Workflow";
import { AgentSystem } from "@/components/landing/AgentSystem";
import { Metrics } from "@/components/landing/Metrics";
import { About } from "@/components/landing/About";
import { Footer } from "@/components/landing/Footer";

export default function HomePage() {
  return (
    <main>
      <Nav />
      <Hero />
      <Problem />
      <Workflow />
      <AgentSystem />
      <Metrics />
      <About />
      <Footer />
    </main>
  );
}
