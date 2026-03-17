import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Standard utility for merging Tailwind classes together.
 * Resolves conflicts between conditional classes (e.g. padding, colors).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
