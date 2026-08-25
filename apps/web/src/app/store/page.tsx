"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { detectGeoLocation } from "@/lib/geo";


export default function StoreRedirect() {
  const router = useRouter();

  useEffect(() => {
    detectGeoLocation().then(geo => {
      if (geo.is_nepal) {
        localStorage.setItem("region", "nepal");
        router.replace("/nepal");
      } else {
        const savedRegion = localStorage.getItem("region");
        if (savedRegion === "nepal") {
          router.replace("/nepal");
        } else if (savedRegion === "worldwide") {
          router.replace("/worldwide");
        } else {
          router.replace("/");
        }
      }
    });
  }, [router]);


  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center">
      <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      <p className="text-xs font-semibold text-muted-foreground mt-3">Routing to your store region...</p>
    </div>
  );
}
