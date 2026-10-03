import type { ShoppingListItemPublic } from "@/client"

/**
 * Items there is still something to buy for. One fully covered by what is
 * already at home is not part of the shop, so it is left out of previews and
 * progress counts rather than shown as an unchecked line.
 */
export function itemsToBuy(
  items: ShoppingListItemPublic[] | undefined,
): ShoppingListItemPublic[] {
  return (items ?? []).filter((item) => item.quantity_to_buy > 0)
}
