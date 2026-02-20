import { useState } from 'react'
import { Plus, X, Lightbulb, FileText, Play, Check, Loader2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from './Toast'

interface QuickActionModalProps {
  title: string
  icon: React.ReactNode
  onClose: () => void
  children: React.ReactNode
}

function QuickActionModal({ title, icon, onClose, children }: QuickActionModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            {icon}
            <h3 className="font-medium">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-4">
          {children}
        </div>
      </div>
    </div>
  )
}

interface ActionButtonProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
  color?: string
}

function ActionButton({ icon, label, onClick, color = 'bg-accent' }: ActionButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 ${color} text-white rounded-lg shadow-lg hover:opacity-90 transition-all`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}

export default function QuickActions() {
  const [isOpen, setIsOpen] = useState(false)
  const [activeModal, setActiveModal] = useState<'learning' | 'fact' | 'episode' | null>(null)
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  // Learning form state
  const [learning, setLearning] = useState('')
  const [learningCategory, setLearningCategory] = useState('General')

  // Fact form state
  const [factClaim, setFactClaim] = useState('')
  const [factConfidence, setFactConfidence] = useState(0.7)

  // Episode form state
  const [episodeGoal, setEpisodeGoal] = useState('')

  const saveLearning = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/actions/learning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ learning, category: learningCategory }),
      })
      if (!res.ok) throw new Error('Failed to save learning')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artifacts'] })
      setLearning('')
      setActiveModal(null)
      addToast({ type: 'success', title: 'Learning saved', message: `Category: ${learningCategory}` })
    },
    onError: () => {
      addToast({ type: 'error', title: 'Failed to save learning' })
    },
  })

  const storeFact = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/actions/fact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim: factClaim, confidence: factConfidence }),
      })
      if (!res.ok) throw new Error('Failed to store fact')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artifacts'] })
      setFactClaim('')
      setActiveModal(null)
      addToast({ type: 'success', title: 'Fact stored', message: `Confidence: ${Math.round(factConfidence * 100)}%` })
    },
    onError: () => {
      addToast({ type: 'error', title: 'Failed to store fact' })
    },
  })

  const startEpisode = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/actions/episode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: episodeGoal }),
      })
      if (!res.ok) throw new Error('Failed to start episode')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['artifacts'] })
      setEpisodeGoal('')
      setActiveModal(null)
      addToast({ type: 'success', title: 'Episode started', message: episodeGoal.slice(0, 50) })
    },
    onError: () => {
      addToast({ type: 'error', title: 'Failed to start episode' })
    },
  })

  const closeModal = () => {
    setActiveModal(null)
  }

  return (
    <>
      {/* Floating Action Button */}
      <div className="fixed bottom-6 right-6 z-40">
        <div className={`flex flex-col-reverse gap-2 transition-all ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
          <ActionButton
            icon={<Lightbulb className="w-4 h-4" />}
            label="Log Learning"
            onClick={() => { setActiveModal('learning'); setIsOpen(false) }}
            color="bg-warning"
          />
          <ActionButton
            icon={<FileText className="w-4 h-4" />}
            label="Store Fact"
            onClick={() => { setActiveModal('fact'); setIsOpen(false) }}
            color="bg-accent"
          />
          <ActionButton
            icon={<Play className="w-4 h-4" />}
            label="Start Episode"
            onClick={() => { setActiveModal('episode'); setIsOpen(false) }}
            color="bg-success"
          />
        </div>

        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`mt-2 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center transition-transform hover:scale-105 ${isOpen ? 'rotate-45' : ''}`}
        >
          <Plus className="w-6 h-6" />
        </button>
      </div>

      {/* Learning Modal */}
      {activeModal === 'learning' && (
        <QuickActionModal
          title="Log Learning"
          icon={<Lightbulb className="w-5 h-5 text-warning" />}
          onClose={closeModal}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">Category</label>
              <select
                value={learningCategory}
                onChange={(e) => setLearningCategory(e.target.value)}
                className="w-full px-3 py-2 bg-page border border-border rounded text-sm focus:outline-none focus:border-accent"
              >
                <option value="General">General</option>
                <option value="Technical">Technical</option>
                <option value="Process">Process</option>
                <option value="User Preference">User Preference</option>
                <option value="Architecture">Architecture</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Learning</label>
              <textarea
                value={learning}
                onChange={(e) => setLearning(e.target.value)}
                placeholder="What did you learn?"
                rows={3}
                className="w-full px-3 py-2 bg-page border border-border rounded text-sm focus:outline-none focus:border-accent resize-none"
              />
            </div>
            <button
              onClick={() => saveLearning.mutate()}
              disabled={!learning.trim() || saveLearning.isPending}
              className="w-full py-2 bg-warning text-black rounded font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {saveLearning.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              Save Learning
            </button>
          </div>
        </QuickActionModal>
      )}

      {/* Fact Modal */}
      {activeModal === 'fact' && (
        <QuickActionModal
          title="Store Fact"
          icon={<FileText className="w-5 h-5 text-accent" />}
          onClose={closeModal}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">Claim</label>
              <textarea
                value={factClaim}
                onChange={(e) => setFactClaim(e.target.value)}
                placeholder="What is the fact?"
                rows={3}
                className="w-full px-3 py-2 bg-page border border-border rounded text-sm focus:outline-none focus:border-accent resize-none"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Confidence: {Math.round(factConfidence * 100)}%
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={factConfidence}
                onChange={(e) => setFactConfidence(parseFloat(e.target.value))}
                className="w-full accent-accent"
              />
            </div>
            <button
              onClick={() => storeFact.mutate()}
              disabled={!factClaim.trim() || storeFact.isPending}
              className="w-full py-2 bg-accent text-white rounded font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {storeFact.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              Store Fact
            </button>
          </div>
        </QuickActionModal>
      )}

      {/* Episode Modal */}
      {activeModal === 'episode' && (
        <QuickActionModal
          title="Start Episode"
          icon={<Play className="w-5 h-5 text-success" />}
          onClose={closeModal}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">Goal</label>
              <textarea
                value={episodeGoal}
                onChange={(e) => setEpisodeGoal(e.target.value)}
                placeholder="What are you trying to achieve?"
                rows={3}
                className="w-full px-3 py-2 bg-page border border-border rounded text-sm focus:outline-none focus:border-accent resize-none"
              />
            </div>
            <button
              onClick={() => startEpisode.mutate()}
              disabled={!episodeGoal.trim() || startEpisode.isPending}
              className="w-full py-2 bg-success text-white rounded font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {startEpisode.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Start Episode
            </button>
          </div>
        </QuickActionModal>
      )}
    </>
  )
}
