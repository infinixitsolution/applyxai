import type { CheckoutOptions } from "../types";

const SCRIPT_URL = "https://checkout.razorpay.com/v1/checkout.js";

export interface RazorpaySuccess {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open: () => void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

/** A problem opening the payment window; the message is written for users. */
export class CheckoutError extends Error {}

let loading: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      loading = null;
      script.remove();
      reject(new CheckoutError("Couldn't load the payment window. Check your connection or ad blocker and try again."));
    };
    document.head.appendChild(script);
  });
  return loading;
}

/**
 * Opens Razorpay Checkout. Resolves with what Checkout returns (which the server then verifies),
 * or null if the user closes the window. A failed attempt is shown inside Checkout, which lets
 * the user try again, so it doesn't end the promise.
 */
export async function openRazorpayCheckout(options: CheckoutOptions): Promise<RazorpaySuccess | null> {
  await loadScript();
  const Razorpay = window.Razorpay;
  if (!Razorpay) throw new CheckoutError("Couldn't load the payment window. Please try again.");
  return new Promise((resolve) => {
    new Razorpay({
      ...options,
      theme: options.theme ?? { color: "#4f46e5" },
      handler: (response: RazorpaySuccess) => resolve(response),
      modal: { ...(options.modal ?? {}), ondismiss: () => resolve(null) },
    }).open();
  });
}
