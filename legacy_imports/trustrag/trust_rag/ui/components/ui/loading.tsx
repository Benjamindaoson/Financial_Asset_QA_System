"use client";

import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const spinnerVariants = cva(
  "animate-spin rounded-full border-2 border-gray-300 border-t-transparent",
  {
    variants: {
      size: {
        xs: "h-3 w-3",
        sm: "h-4 w-4",
        md: "h-6 w-6",
        lg: "h-8 w-8",
        xl: "h-12 w-12",
      },
      color: {
        default: "border-gray-300 border-t-blue-500",
        white: "border-white/20 border-t-white",
        primary: "border-primary/20 border-t-primary",
      },
    },
    defaultVariants: {
      size: "md",
      color: "default",
    },
  }
);

export interface SpinnerProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof spinnerVariants> {}

const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ className, size, color, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(spinnerVariants({ size, color }), className)}
      {...props}
    />
  )
);
Spinner.displayName = "Spinner";

interface LoadingProps extends React.HTMLAttributes<HTMLDivElement> {
  text?: string;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  overlay?: boolean;
  fullScreen?: boolean;
}

const Loading = React.forwardRef<HTMLDivElement, LoadingProps>(
  ({ className, text, size = "md", overlay = false, fullScreen = false, ...props }, ref) => {
    const content = (
      <div className="flex flex-col items-center justify-center space-y-2">
        <Spinner size={size} />
        {text && (
          <p className="text-sm text-muted-foreground animate-pulse">
            {text}
          </p>
        )}
      </div>
    );

    if (fullScreen) {
      return (
        <div
          ref={ref}
          className={cn(
            "fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm",
            className
          )}
          {...props}
        >
          {content}
        </div>
      );
    }

    if (overlay) {
      return (
        <div
          ref={ref}
          className={cn(
            "absolute inset-0 z-10 flex items-center justify-center bg-background/60 backdrop-blur-sm rounded-lg",
            className
          )}
          {...props}
        >
          {content}
        </div>
      );
    }

    return (
      <div
        ref={ref}
        className={cn("flex items-center justify-center p-4", className)}
        {...props}
      >
        {content}
      </div>
    );
  }
);
Loading.displayName = "Loading";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "circular" | "rectangular";
  width?: string | number;
  height?: string | number;
  count?: number;
}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, variant = "text", width, height, count = 1, ...props }, ref) => {
    const getVariantClasses = () => {
      switch (variant) {
        case "circular":
          return "rounded-full";
        case "rectangular":
          return "rounded-md";
        default:
          return "rounded";
      }
    };

    const skeletonClass = cn(
      "animate-pulse bg-muted",
      getVariantClasses(),
      className
    );

    const style = {
      width: typeof width === "number" ? `${width}px` : width,
      height: typeof height === "number" ? `${height}px` : height,
    };

    if (count === 1) {
      return (
        <div
          ref={ref}
          className={skeletonClass}
          style={style}
          {...props}
        />
      );
    }

    return (
      <div ref={ref} className="space-y-2" {...props}>
        {Array.from({ length: count }).map((_, index) => (
          <div
            key={index}
            className={skeletonClass}
            style={style}
          />
        ))}
      </div>
    );
  }
);
Skeleton.displayName = "Skeleton";

export { Spinner, Loading, Skeleton };







