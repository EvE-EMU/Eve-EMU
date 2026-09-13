import { redirectToDesktop } from "@/lib/redirectToDesktop";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export default async function LegacyHubPage({ searchParams }: Props) {
  redirectToDesktop(await searchParams);
}
