import { redirect } from 'next/navigation';

export default function Home() {
  // Directly route to login. The layout will mount the enterprise Auth system.
  redirect('/login');
}
