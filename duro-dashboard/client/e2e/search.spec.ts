import { test, expect } from '@playwright/test'

test.describe('Search Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/search')
  })

  test('should display search interface', async ({ page }) => {
    // Search input should be visible and focused
    const searchInput = page.getByPlaceholder(/Search your memory/)
    await expect(searchInput).toBeVisible()

    // Search tips should be shown when no query
    await expect(page.getByText('Search Tips')).toBeVisible()

    // Filter dropdown should be available
    await expect(page.getByRole('combobox')).toBeVisible()
  })

  test('should show empty state when no query', async ({ page }) => {
    await expect(page.getByText('Start typing to search your memory')).toBeVisible()
  })

  test('should filter by artifact type', async ({ page }) => {
    const filterSelect = page.getByRole('combobox')

    // Select Facts filter
    await filterSelect.selectOption('fact')
    await expect(filterSelect).toHaveValue('fact')

    // Select Decisions filter
    await filterSelect.selectOption('decision')
    await expect(filterSelect).toHaveValue('decision')

    // Reset to All
    await filterSelect.selectOption('')
    await expect(filterSelect).toHaveValue('')
  })

  test('should clear search with X button', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/Search your memory/)

    // Type a query
    await searchInput.fill('test query')
    await expect(searchInput).toHaveValue('test query')

    // Clear button should appear
    const clearButton = page.locator('button').filter({ has: page.locator('svg.lucide-x') })
    await clearButton.click()

    // Input should be cleared
    await expect(searchInput).toHaveValue('')
  })

  test('should perform search and show results or no results', async ({ page }) => {
    const searchInput = page.getByPlaceholder(/Search your memory/)

    // Type a search query
    await searchInput.fill('authentication')

    // Wait for debounce and results
    await page.waitForTimeout(500)

    // Should show either results or "No results found"
    const hasResults = await page.getByText(/\d+ results? for/).isVisible().catch(() => false)
    const noResults = await page.getByText('No results found').isVisible().catch(() => false)

    expect(hasResults || noResults).toBeTruthy()
  })
})

test.describe('Search - Recent Searches', () => {
  test('should save and display recent searches', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByPlaceholder(/Search your memory/)

    // Perform a search
    await searchInput.fill('test query one')
    await searchInput.press('Enter')

    // Clear and check recent searches appear
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-x') }).click()

    // Recent searches section should appear
    await expect(page.getByText('Recent searches')).toBeVisible()
    await expect(page.getByRole('button', { name: 'test query one' })).toBeVisible()
  })

  test('should clear recent searches', async ({ page }) => {
    // Set up localStorage with a recent search
    await page.addInitScript(() => {
      localStorage.setItem('duro-recent-searches', JSON.stringify(['previous search']))
    })

    await page.goto('/search')

    // Recent searches should be visible
    await expect(page.getByText('Recent searches')).toBeVisible()

    // Click clear
    await page.getByRole('button', { name: 'Clear' }).click()

    // Recent searches should be gone
    await expect(page.getByText('Recent searches')).not.toBeVisible()
  })
})
