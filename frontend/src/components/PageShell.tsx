"use client";

import styles from "./PageShell.module.css";

interface PageShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export default function PageShell({ title, subtitle, children }: PageShellProps) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <h1 className={styles.title}>{title}</h1>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </header>
      <div className={styles.content}>{children}</div>
    </div>
  );
}
