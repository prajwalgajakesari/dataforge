import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ConnectSource } from "@/components/flows/ConnectSource"
import { SelectStrategy } from "@/components/flows/SelectStrategy"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { ModelingCanvas } from "@/components/canvas/ModelingCanvas"

type Step = "source" | "strategy" | "canvas"

function App() {
  const [step, setStep] = useState<Step>("source")
  const [source, setSource] = useState<string | null>(null)
  const [strategy, setStrategy] = useState<string | null>(null)

  const handleSourceSelect = (sourceId: string) => {
    setSource(sourceId)
    setStep("strategy")
  }

  const handleStrategySelect = (strategyId: string) => {
    setStrategy(strategyId)
    // TODO: Initialize backend session here
    setStep("canvas")
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="border-b h-14 flex items-center px-6">
        <div className="flex items-center gap-2 font-bold text-xl">
          <div className="w-8 h-8 rounded bg-primary/20 flex items-center justify-center text-primary">
            D
          </div>
          DataForge
        </div>
      </header>

      <main className="flex-1 flex flex-col p-6 max-w-5xl mx-auto w-full">
        {step !== "canvas" && (
          <div className="flex items-center justify-center gap-4 mb-12 mt-8">
            <StepIndicator
              active={step === "source"}
              completed={source !== null}
              label="Source"
              number={1}
            />
            <div className={cn("w-16 h-0.5 transition-colors", source !== null ? "bg-primary" : "bg-muted")} />
            <StepIndicator
              active={step === "strategy"}
              completed={strategy !== null}
              label="Strategy"
              number={2}
            />
            <div className={cn("w-16 h-0.5 transition-colors", strategy !== null ? "bg-primary" : "bg-muted")} />
            <StepIndicator
              active={false}
              completed={false}
              label="Design"
              number={3}
            />
          </div>
        )}

        <AnimatePresence mode="wait">
          {step === "source" && (
            <motion.div
              key="source"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="flex-1"
            >
              <ConnectSource onSelect={handleSourceSelect} />
            </motion.div>
          )}

          {step === "strategy" && (
            <motion.div
              key="strategy"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="flex-1"
            >
              <div className="mb-6">
                <Button variant="ghost" onClick={() => setStep("source")}>
                  ← Back to Source
                </Button>
              </div>
              <SelectStrategy onSelect={handleStrategySelect} />
            </motion.div>
          )}

          {step === "canvas" && (
            <motion.div
              key="canvas"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex-1 flex flex-col h-full"
            >
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold">Data Model</h2>
                  <p className="text-muted-foreground text-sm">Design your schema ({strategy})</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setStep("strategy")}>Back</Button>
                  <Button>Generate Code</Button>
                </div>
              </div>
              <ModelingCanvas />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}

function StepIndicator({
  active,
  completed,
  label,
  number,
}: {
  active: boolean
  completed: boolean
  label: string
  number: number
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm transition-colors",
          completed
            ? "bg-primary text-primary-foreground"
            : active
              ? "border-2 border-primary text-primary"
              : "border-2 border-muted text-muted-foreground"
        )}
      >
        {completed ? "✓" : number}
      </div>
      <span
        className={cn(
          "text-xs font-medium transition-colors",
          active || completed ? "text-foreground" : "text-muted-foreground"
        )}
      >
        {label}
      </span>
    </div>
  )
}

export default App
