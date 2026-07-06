import { Nav } from "@/components/landing/Nav";
import { ProfileView } from "@/components/profile/ProfileView";

export const metadata = {
  title: "Profile & Account — ClaimSight India",
  description: "Manage your ClaimSight profile, photo and contact details.",
};

export default function ProfilePage() {
  return (
    <main>
      <Nav />
      <ProfileView />
    </main>
  );
}
