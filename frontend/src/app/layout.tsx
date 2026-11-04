import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CineFinder — Find films that feel like you",
  description:
    "Discover your next favourite film with personalized, machine-learning-powered movie recommendations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
