"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const LINKS = [
  { href: "/", label: "Today", icon: "⚡" },
  { href: "/running", label: "Running", icon: "🏃" },
  { href: "/health", label: "Health", icon: "💚" },
  { href: "/strength", label: "Strength", icon: "🏋️" },
  { href: "/weekly-review", label: "Review", icon: "📊" },
  { href: "/debug", label: "Debug", icon: "🔧" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <nav className={styles.nav}>
      <Link href="/" className={styles.brand}>
        <span className={styles.brandIcon}>△</span>
        <span className={styles.brandText}>Peakwise</span>
      </Link>
      <div className={styles.links}>
        {LINKS.map(({ href, label, icon }) => (
          <Link
            key={href}
            href={href}
            className={`${styles.link} ${pathname === href ? styles.active : ""}`}
          >
            <span className={styles.linkIcon}>{icon}</span>
            <span className={styles.linkLabel}>{label}</span>
          </Link>
        ))}
      </div>
    </nav>
  );
}
