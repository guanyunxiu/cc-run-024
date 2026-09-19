import { z } from 'zod'

export const residentSchema = z.object({
  name: z.string().min(1, '请填写姓名'),
  gender: z.enum(['male', 'female']),
  age: z.coerce.number().int().min(60).max(120),
  height_cm: z.coerce.number().min(130).max(210),
  weight_kg: z.coerce.number().min(30).max(150),
  activity_level: z.string(),
  swallowing_level: z.coerce.number().int().min(0).max(7),
  chronic_conditions: z.array(z.string()).default([]),
  allergies: z.array(z.string()).default([]),
  dislikes: z.array(z.string()).default([]),
  religion: z.string().default('none'),
  medications: z.array(z.string()).default([]),
  nutrition_goal_type: z.enum(['maintain', 'lose', 'gain']).default('maintain'),
  note: z.string().default(''),
})

export type ResidentFormValues = z.infer<typeof residentSchema>
