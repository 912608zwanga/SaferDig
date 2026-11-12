import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaferDig — Check before you confirm",
  description: "A simple transaction-intention check prototype for safer digital payments."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
