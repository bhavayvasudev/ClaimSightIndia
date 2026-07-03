import Link from "next/link";
import type { ReactNode } from "react";

type PillButtonProps = {
  children: ReactNode;
  href?: string;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost";
  size?: "md" | "lg";
};

const base =
  "inline-flex items-center justify-center rounded-full font-medium tracking-body transition-colors duration-300";

const variants = {
  primary: "bg-lavender text-white shadow-subtle hover:bg-iris",
  ghost: "bg-mist text-graphite hover:bg-fog",
};

const sizes = {
  md: "px-5 py-2.5 text-[14px]",
  lg: "px-7 py-3.5 text-[15px]",
};

export function PillButton({
  children,
  href,
  onClick,
  type = "button",
  variant = "primary",
  size = "md",
}: PillButtonProps) {
  const className = `${base} ${variants[variant]} ${sizes[size]}`;
  if (href) {
    return (
      <Link href={href} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <button type={type} onClick={onClick} className={className}>
      {children}
    </button>
  );
}
