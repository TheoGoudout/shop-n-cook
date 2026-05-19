import { describe, expect, it } from "vitest"
import { parsedRecipeToCreate } from "../api"
import type { ParsedRecipe } from "../client/types.gen"

describe("parsedRecipeToCreate", () => {
  const baseParsed: ParsedRecipe = {
    title: "Pasta Carbonara",
    description: "A classic Roman pasta dish",
    servings: 2,
    prep_time_minutes: 10,
    cook_time_minutes: 20,
    source_url: "https://example.com/pasta",
    image_url: "https://example.com/pasta.jpg",
    ingredients: [
      { name: "spaghetti", quantity: 200, unit: "g" },
      { name: "eggs", quantity: 3, unit: "piece" },
      {
        name: "pancetta",
        quantity: 100,
        unit: "g",
        notes: "diced",
      },
    ],
    steps: [
      { instruction: "Boil the spaghetti.", ingredient_names: ["spaghetti"] },
      {
        instruction: "Mix eggs and pancetta.",
        ingredient_names: ["eggs", "pancetta"],
      },
      {
        instruction: "Combine everything.",
        ingredient_names: ["spaghetti", "eggs", "pancetta"],
      },
    ],
  }

  it("maps top-level fields", () => {
    const result = parsedRecipeToCreate(baseParsed)
    expect(result.title).toBe("Pasta Carbonara")
    expect(result.description).toBe("A classic Roman pasta dish")
    expect(result.servings).toBe(2)
    expect(result.prep_time_minutes).toBe(10)
    expect(result.cook_time_minutes).toBe(20)
    expect(result.source_url).toBe("https://example.com/pasta")
    expect(result.image_url).toBe("https://example.com/pasta.jpg")
  })

  it("maps ingredients using ingredient_name (not ingredient_id)", () => {
    const result = parsedRecipeToCreate(baseParsed)
    expect(result.ingredients).toHaveLength(3)
    expect(result.ingredients?.[0]).toMatchObject({
      ingredient_name: "spaghetti",
      quantity: 200,
      unit: "g",
    })
    expect(result.ingredients?.[2]).toMatchObject({
      ingredient_name: "pancetta",
      notes: "diced",
    })
  })

  it("maps step ingredient_names to correct ingredient_indices", () => {
    const result = parsedRecipeToCreate(baseParsed)
    expect(result.steps?.[0]).toMatchObject({
      step_number: 1,
      ingredient_indices: [0],
    })
    expect(result.steps?.[1]).toMatchObject({
      step_number: 2,
      ingredient_indices: [1, 2],
    })
    expect(result.steps?.[2]).toMatchObject({
      step_number: 3,
      ingredient_indices: [0, 1, 2],
    })
  })

  it("assigns step_number starting from 1", () => {
    const result = parsedRecipeToCreate(baseParsed)
    expect(result.steps?.map((s) => s.step_number)).toEqual([1, 2, 3])
  })

  it("filters out unknown ingredient names from step indices", () => {
    const parsed: ParsedRecipe = {
      ...baseParsed,
      steps: [
        {
          instruction: "Use mystery ingredient.",
          ingredient_names: ["spaghetti", "unknown-ingredient"],
        },
      ],
    }
    const result = parsedRecipeToCreate(parsed)
    expect(result.steps?.[0]?.ingredient_indices).toEqual([0])
  })

  it("handles steps with no ingredient references", () => {
    const parsed: ParsedRecipe = {
      ...baseParsed,
      steps: [{ instruction: "Season to taste.", ingredient_names: [] }],
    }
    const result = parsedRecipeToCreate(parsed)
    expect(result.steps?.[0]?.ingredient_indices).toEqual([])
  })

  it("handles recipe with undefined ingredients and steps", () => {
    const parsed: ParsedRecipe = { title: "Simple recipe" }
    const result = parsedRecipeToCreate(parsed)
    expect(result.ingredients).toEqual([])
    expect(result.steps).toEqual([])
  })
})
