import "./globals.css";
import React from "react";
import { Sidebar } from "@/components/Sidebar";
import { Navbar } from "@/components/Navbar";

export const metadata = {
  title: "EDUCORE AI - PS2 Subjective Grading Assistant",
  description: "Automated Formative Assessment and Intelligent Subjective Grading Assistant for Higher Education",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen bg-slate-50 text-slate-900">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Navbar />
          <main className="flex-1 p-8 overflow-y-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}

