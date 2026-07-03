export function VehicleIllustration() {
  return (
    <svg
      viewBox="0 0 640 320"
      role="img"
      aria-label="Flat line illustration of a sedan being analyzed by ClaimSight"
      className="h-auto w-full"
    >
      <ellipse cx="320" cy="298" rx="248" ry="10" fill="#e8e8e8" />

      {/* body */}
      <path
        d="M70 210
           C70 186 90 176 118 174
           L168 172
           C186 130 224 96 268 92
           L392 92
           C432 96 466 126 484 172
           L534 176
           C558 178 574 190 574 212
           L574 226
           C574 236 566 244 556 244
           L520 244
           C520 222 502 204 480 204
           C458 204 440 222 440 244
           L212 244
           C212 222 194 204 172 204
           C150 204 132 222 132 244
           L94 244
           C82 244 70 236 70 224
           Z"
        fill="#ffffff"
        stroke="#181925"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />

      {/* roofline / cabin */}
      <path
        d="M182 172
           C200 132 232 100 270 96
           L390 96
           C426 100 456 128 472 172
           Z"
        fill="none"
        stroke="#181925"
        strokeWidth="1.5"
      />

      {/* windows */}
      <path
        d="M198 168
           C214 138 238 112 268 108
           L322 108
           L322 168
           Z"
        fill="#f5f5f5"
        stroke="#181925"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M330 108
           L388 108
           C412 114 434 138 452 168
           L330 168
           Z"
        fill="#f5f5f5"
        stroke="#181925"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <line x1="326" y1="106" x2="326" y2="170" stroke="#181925" strokeWidth="1.5" />

      {/* door line */}
      <line x1="326" y1="176" x2="326" y2="244" stroke="#181925" strokeWidth="1.5" opacity="0.4" />

      {/* handles */}
      <rect x="284" y="192" width="20" height="4" rx="2" fill="#181925" />
      <rect x="376" y="192" width="20" height="4" rx="2" fill="#181925" />

      {/* headlight / taillight */}
      <rect x="556" y="190" width="16" height="10" rx="4" fill="#918df6" />
      <rect x="70" y="190" width="14" height="10" rx="4" fill="#181925" opacity="0.5" />

      {/* front number plate */}
      <rect x="532" y="216" width="38" height="14" rx="3" fill="#ffffff" stroke="#181925" strokeWidth="1.2" />
      <line x1="538" y1="223" x2="564" y2="223" stroke="#999999" strokeWidth="2" strokeLinecap="round" />

      {/* damage crease on front fender */}
      <path
        d="M492 186 C500 192 506 200 508 210"
        fill="none"
        stroke="#999999"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="4 4"
      />

      {/* wheels */}
      <circle cx="172" cy="244" r="38" fill="#181925" />
      <circle cx="172" cy="244" r="14" fill="#fafafa" />
      <circle cx="480" cy="244" r="38" fill="#181925" />
      <circle cx="480" cy="244" r="14" fill="#fafafa" />
    </svg>
  );
}
