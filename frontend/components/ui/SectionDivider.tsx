/** Elegant section boundary: a hairline that fades out before the edges. */
export function SectionDivider() {
  return (
    <div
      aria-hidden
      className="mx-auto h-px w-full max-w-content bg-gradient-to-r from-transparent via-fog to-transparent"
    />
  );
}
