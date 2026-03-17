import * as React from "react"
import { cn } from "@/shared/lib/utils"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "ghost" | "link"
  size?: "default" | "sm" | "lg" | "icon"
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    
    // Base styles (Enterprise Radix/Shadcn pattern)
    let compClass = "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
    
    // Variant mapping
    if (variant === "default") {
      compClass += " bg-primary text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(37,99,235,0.4)]"
    } else if (variant === "destructive") {
        compClass += " bg-red-600 text-white hover:bg-red-600/90"
    } else if (variant === "outline") {
        compClass += " border border-border bg-card hover:bg-border text-foreground hover:text-white"
    } else if (variant === "ghost") {
        compClass += " hover:bg-border hover:text-white text-gray-300"
    } else if (variant === "link") {
        compClass += " text-primary underline-offset-4 hover:underline"
    }

    // Size mapping
    if (size === "default") {
        compClass += " h-10 px-4 py-2"
    } else if (size === "sm") {
        compClass += " h-9 rounded-md px-3"
    } else if (size === "lg") {
        compClass += " h-11 rounded-md px-8"
    } else if (size === "icon") {
        compClass += " h-10 w-10"
    }

    return (
      <button
        className={cn(compClass, className)}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
