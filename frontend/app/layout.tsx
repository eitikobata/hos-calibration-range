import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HOS Calibration Range",
  description: "Actuator and stabilization tuning test bench",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
