import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('should load overview page by default', async ({ page }) => {
    await page.goto('/')

    // Should redirect to /overview
    await expect(page).toHaveURL(/.*overview/)

    // Header should be visible
    await expect(page.locator('header')).toBeVisible()

    // DURO branding should be present
    await expect(page.getByText('DURO')).toBeVisible()
  })

  test('should navigate between pages via sidebar', async ({ page }) => {
    await page.goto('/overview')

    // Navigate to Search
    await page.getByRole('link', { name: 'Search' }).click()
    await expect(page).toHaveURL(/.*search/)
    await expect(page.getByText('Semantic Search')).toBeVisible()

    // Navigate to Memory
    await page.getByRole('link', { name: 'Memory' }).click()
    await expect(page).toHaveURL(/.*memory/)

    // Navigate to Episodes
    await page.getByRole('link', { name: 'Episodes' }).click()
    await expect(page).toHaveURL(/.*episodes/)
    await expect(page.getByText('Episode Timeline')).toBeVisible()

    // Navigate to Settings
    await page.getByRole('link', { name: 'Settings' }).click()
    await expect(page).toHaveURL(/.*settings/)
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  })

  test('should show active state on current nav item', async ({ page }) => {
    await page.goto('/overview')

    const overviewLink = page.getByRole('link', { name: 'Overview' })
    await expect(overviewLink).toHaveClass(/text-accent/)

    // Navigate and check active state changes
    await page.getByRole('link', { name: 'Search' }).click()
    const searchLink = page.getByRole('link', { name: 'Search' })
    await expect(searchLink).toHaveClass(/text-accent/)
  })

  test('should display system status in sidebar', async ({ page }) => {
    await page.goto('/overview')

    // System status panel should be visible on desktop
    await expect(page.getByText('System')).toBeVisible()
    await expect(page.getByText('Database')).toBeVisible()
  })
})

test.describe('Layout', () => {
  test('should have proper page structure', async ({ page }) => {
    await page.goto('/overview')

    // Sidebar exists
    await expect(page.locator('aside')).toBeVisible()

    // Main content area exists
    await expect(page.locator('main')).toBeVisible()

    // Header with controls
    await expect(page.locator('header')).toBeVisible()
  })

  test('should show stats grid on overview', async ({ page }) => {
    await page.goto('/overview')

    // Wait for stats to load
    await page.waitForSelector('[class*="grid"]')

    // Check for stat labels
    await expect(page.getByText('Total Artifacts')).toBeVisible()
    await expect(page.getByText('Facts')).toBeVisible()
    await expect(page.getByText('Decisions')).toBeVisible()
  })
})
