BEST ARCHITECTURE

You should KEEP BOTH:

Frontend popup validation
+
Backend enterprise validation

This is how enterprise systems work.

STEP-BY-STEP ARCHITECTURE
FRONTEND VALIDATION FLOW

When user types:

Building_limit = abc

frontend instantly shows:

"Building limit must be numeric"

WITHOUT API call.

BACKEND VALIDATION FLOW

When user clicks:

Calculate Premium

backend validation runs:

formula analysis
dependency graph
explainability
profiling
etc.
WHERE FRONTEND VALIDATION SHOULD BE ADDED

Most likely your client form page is:

frontend/app/client/[slug]/page.tsx

This is where:

inputs render
Calculate Premium button exists

So popup validation logic belongs HERE.

WHAT FILES SHOULD BE CREATED

BEST CLEAN STRUCTURE:

frontend/lib/validation/

Inside create:

frontend/lib/validation/inputValidation.ts
PURPOSE OF THIS FILE

This file will contain:

numeric validation
range validation
required validation
popup error generation
FLOW
User types input
   ↓
validateInput()
   ↓
frontend state updates
   ↓
error popup/message shown
WHAT CODE SHOULD EXIST
FILE 1
frontend/lib/validation/inputValidation.ts

This file should contain functions like:

export function validateInput(field, value) {

   const errors = []

   if (field.includes("year")) {
      if (isNaN(Number(value))) {
         errors.push("Year must be numeric")
      }
   }

   if (field.includes("limit")) {
      if (Number(value) > 1000000) {
         errors.push("Limit exceeded")
      }
   }

   return errors
}
FILE 2

Main frontend page:

frontend/app/client/[slug]/page.tsx

This file should:

call validateInput()
store errors in state
show popup/messages
WHAT CHANGES NEEDED IN page.tsx
1. IMPORT VALIDATOR
import { validateInput } from "@/lib/validation/inputValidation"
2. ADD ERROR STATE
const [validationErrors, setValidationErrors] = useState({})
3. ON INPUT CHANGE

Inside existing input handler:

const errors = validateInput(fieldName, value)

setValidationErrors(prev => ({
   ...prev,
   [fieldName]: errors
}))
4. SHOW ERROR BELOW FIELD

Below input field:

{validationErrors[fieldName]?.map((err) => (
   <p className="text-red-500 text-sm">{err}</p>
))}
RESULT

Now when user types:

abc

in numeric field:

popup/error appears instantly.