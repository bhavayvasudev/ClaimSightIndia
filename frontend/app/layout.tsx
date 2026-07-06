import { Inter } from "next/font/google";
import { SessionProvider } from "next-auth/react";
import "./globals.css";
import { SmoothScroll } from "@/components/providers/SmoothScroll";

const sans = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

export const metadata = {
  title: "ClaimSight India — AI-Powered Multimodal Claim Triage",
  description:
    "An AI system that analyzes vehicle damage images, insurance policy PDFs, vehicle registration numbers, and accident narratives to generate structured insurance claim triage reports.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        <SessionProvider>
          <SmoothScroll>{children}</SmoothScroll>
        </SessionProvider>
        <div className="grain" aria-hidden />
      </body>
    </html>
  );
}
