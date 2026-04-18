export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      {children}
    </div>
  );
}
