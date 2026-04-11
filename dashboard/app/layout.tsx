import "./globals.css";

export const metadata = {
  title: "Spectrum Systems Dashboard",
  description: "Live operational dashboard for Spectrum Systems",
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
