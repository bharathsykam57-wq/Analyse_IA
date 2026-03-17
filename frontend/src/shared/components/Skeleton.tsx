"use client";

import { cn } from "@/shared/lib/utils";

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  count?: number;
  circle?: boolean;
}

export function Skeleton({
  className,
  width = "100%",
  height = "20px",
  count = 1,
  circle = false,
}: SkeletonProps) {
  const style = {
    width: typeof width === "number" ? `${width}px` : width,
    height: typeof height === "number" ? `${height}px` : height,
    borderRadius: circle ? "50%" : "0.375rem",
  };

  const skeletons = Array.from({ length: count }).map((_, i) => (
    <div
      key={i}
      className={cn(
        "bg-gradient-to-r from-gray-700 via-gray-600 to-gray-700 animate-pulse",
        className
      )}
      style={style}
    />
  ));

  return count === 1 ? skeletons[0] : <div className="space-y-2">{skeletons}</div>;
}

export function SkeletonList({ count = 5, className }: { count?: number; className?: string }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={cn("space-y-2", className)}>
          <Skeleton height="20px" width="80%" />
          <Skeleton height="16px" width="60%" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonCard({
  count = 3,
  className,
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "p-4 rounded-lg bg-gray-800/50 border border-gray-700/30 space-y-3",
            className
          )}
        >
          <Skeleton height="24px" width="70%" />
          <Skeleton height="16px" width="100%" />
          <Skeleton height="16px" width="90%" />
        </div>
      ))}
    </div>
  );
}
