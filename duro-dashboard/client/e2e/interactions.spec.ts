import { test, expect } from '@playwright/test'

test.describe('Theme Toggle', () => {
  test('should toggle between dark and light theme', async ({ page }) => {
    await page.goto('/overview')

    // Default should be dark theme
    const html = page.locator('html')
    await expect(html).toHaveAttribute('data-theme', 'dark')

    // Click theme toggle in header (sun icon for dark mode)
    const themeToggle = page.locator('header button[title*="light mode"]')
    await themeToggle.click()

    // Should switch to light theme
    await expect(html).toHaveAttribute('data-theme', 'light')

    // Toggle back to dark
    const darkToggle = page.locator('header button[title*="dark mode"]')
    await darkToggle.click()
    await expect(html).toHaveAttribute('data-theme', 'dark')
  })

  test('should persist theme preference', async ({ page }) => {
    await page.goto('/overview')

    // Switch to light theme
    const themeToggle = page.locator('header button[title*="light mode"]')
    await themeToggle.click()

    // Reload page
    await page.reload()

    // Theme should still be light
    const html = page.locator('html')
    await expect(html).toHaveAttribute('data-theme', 'light')
  })

  test('should change theme from settings page', async ({ page }) => {
    await page.goto('/settings')

    const html = page.locator('html')

    // Find the Dark/Light toggle buttons in settings
    const lightButton = page.getByRole('button', { name: 'Light', exact: true })
    await lightButton.click()

    // Theme should change to light
    await expect(html).toHaveAttribute('data-theme', 'light')

    // Switch back to dark
    const darkButton = page.getByRole('button', { name: 'Dark', exact: true })
    await darkButton.click()
    await expect(html).toHaveAttribute('data-theme', 'dark')
  })
})

test.describe('Keyboard Shortcuts', () => {
  test('should navigate to search with / key', async ({ page }) => {
    await page.goto('/overview')

    // Press / to go to search
    await page.keyboard.press('/')

    // Should navigate to search page
    await expect(page).toHaveURL(/.*search/)
  })

  test('should navigate with j/k keys', async ({ page }) => {
    await page.goto('/overview')

    // Press j to go to next page
    await page.keyboard.press('j')
    await expect(page).toHaveURL(/.*search/)

    // Press j again
    await page.keyboard.press('j')
    await expect(page).toHaveURL(/.*memory/)

    // Press k to go back
    await page.keyboard.press('k')
    await expect(page).toHaveURL(/.*search/)

    // Press k again
    await page.keyboard.press('k')
    await expect(page).toHaveURL(/.*overview/)
  })

  test('should not trigger shortcuts when typing in input', async ({ page }) => {
    await page.goto('/search')

    const searchInput = page.getByPlaceholder(/Search your memory/)
    await searchInput.focus()

    // Type 'j' - should go into input, not navigate
    await searchInput.type('jjj')

    // Should still be on search page
    await expect(page).toHaveURL(/.*search/)
    await expect(searchInput).toHaveValue('jjj')
  })
})

test.describe('Refresh Button', () => {
  test('should have refresh button in header', async ({ page }) => {
    await page.goto('/overview')

    const refreshButton = page.locator('header button[title="Refresh all data"]')
    await expect(refreshButton).toBeVisible()

    // Click should not cause error
    await refreshButton.click()
  })
})

test.describe('Mobile Responsiveness', () => {
  test.use({ viewport: { width: 375, height: 667 } })

  test('should show hamburger menu on mobile', async ({ page }) => {
    await page.goto('/overview')

    // Sidebar should be hidden
    const sidebar = page.locator('aside')
    await expect(sidebar).not.toBeInViewport()

    // Hamburger menu should be visible
    const hamburger = page.locator('header button').filter({ has: page.locator('svg.lucide-menu') })
    await expect(hamburger).toBeVisible()

    // Click hamburger to open sidebar
    await hamburger.click()

    // Sidebar should now be visible
    await expect(sidebar).toBeInViewport()

    // Close button should be visible
    const closeButton = page.locator('aside button').filter({ has: page.locator('svg.lucide-x') })
    await expect(closeButton).toBeVisible()

    // Click close
    await closeButton.click()

    // Sidebar should be hidden again
    await expect(sidebar).not.toBeInViewport()
  })

  test('should close sidebar on Escape key', async ({ page }) => {
    await page.goto('/overview')

    // Open sidebar
    const hamburger = page.locator('header button').filter({ has: page.locator('svg.lucide-menu') })
    await hamburger.click()

    const sidebar = page.locator('aside')
    await expect(sidebar).toBeInViewport()

    // Press Escape
    await page.keyboard.press('Escape')

    // Sidebar should close
    await expect(sidebar).not.toBeInViewport()
  })
})
