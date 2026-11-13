# EVO in software development

EVO is short for **EVO**lutionary Value Delivery. It is also known as Evolutionary
Project Management, or just Evo. Tom Gilb built the method and has used it since 1960.
Several Agile Manifesto signers describe it as the original agile approach.

This page is the software development overview: what EVO is, how one delivery step
works, what Planguage adds, how the method compares to Scrum and XP, and where it is
genuinely hard to apply.

The short version:

> Deliver small steps of measurable stakeholder value, measure what each step actually
> changed, and let the measurement decide what the next step is.

That sounds obvious. The difference is in the details: EVO insists that the
requirements, the estimates and the measurements all use the same numeric scale, so
that "we delivered value" is a checkable statement and not a feeling.

## Contents

- [Where it comes from](#where-it-comes-from)
- [The problem EVO attacks](#the-problem-evo-attacks)
- [The EVO loop](#the-evo-loop)
- [Quantify first: the top ten](#quantify-first-the-top-ten)
- [Planguage: requirements you can measure](#planguage-requirements-you-can-measure)
- [Impact estimation: choosing the next step](#impact-estimation-choosing-the-next-step)
- [The ten Evo principles](#the-ten-evo-principles)
- [What "done" means](#what-done-means)
- [Architecture and technical debt are requirements](#architecture-and-technical-debt-are-requirements)
- [EVO compared with Scrum, XP and waterfall](#evo-compared-with-scrum-xp-and-waterfall)
- [Common misreadings](#common-misreadings)
- [When EVO is hard](#when-evo-is-hard)
- [Introducing EVO without a revolution](#introducing-evo-without-a-revolution)
- [Try it this week](#try-it-this-week)
- [Glossary](#glossary)
- [References](#references)

## Where it comes from

The origin story Gilb still tells: in 1960 he ran an invoicing project at Brodrene
Dobloug in Oslo as 20 steps of value delivery. Each step delivered something tangible
to a stakeholder. Nobody called it a methodology at the time.

The milestones that matter for credibility:

| Year | What happened |
| --- | --- |
| 1960 | First Evo-style project delivery, Oslo |
| 1970s and 1980s | Method formalised as Evolutionary Project Management |
| 1980 | IBM adopts quantified quality goals company wide |
| 1988 | HP adopts Evo and software inspection |
| 2005 | *Competitive Engineering*, the Planguage handbook, is published |
| 2012 | Intel reports about 17,000 engineers voluntarily adopting Planguage |
| 2015 | Gilb and Gilb publish the InfoQ restatement of Evo |
| 2017 | Tom Gilb presents "Evo: The Most Advanced Agile Process" at AgileByExample |

The intellectual lineage is the Deming and Shewhart **PDSA** cycle: plan, do, study,
act. Gilb's own description is that Evo is a specialized variant of PDSA where the
"study" part uses hard measured facts against an initial quantified hypothesis. He
calls that the scientific method, and he means it literally: predict, then check.

This is worth pausing on. Most agile practice also loops. The EVO claim is not about
looping, it is about what travels around the loop. In Scrum the artifact that travels
is a backlog item and the evidence is a demo. In EVO the artifact is a quantified
objective and the evidence is a measurement on a defined scale.

## The problem EVO attacks

Gilb's argument in the 2015 InfoQ article is blunt:

- Agile methods focus on delivering **code** to **users**.
- Stakeholders are wider than users: operators, maintainers, regulators, the business,
  the support desk, future teams.
- The only reason to build an IT system is to change **performance attributes**, that
  is, how well the system does something. Basic business functions already existed
  before the software: banks lent money before computers, cinemas sold tickets before
  computers.
- Therefore the value of an IT system lives in qualities like speed, security,
  usability, cost of operation and maintainability. Those are exactly the things agile
  teams usually leave unquantified.
- Bug fixing is not a quality strategy. It is cleanup after the fact.

So the method is a reaction to two failure patterns:

1. **Activity without value.** Teams report velocity, story points and completed
   tickets, but cannot say whether the customer is better off.
2. **Quality as an afterthought.** Security, usability and maintainability are treated
   as constraints discovered late, instead of as objectives with target levels and
   meters.

That second one is why EVO keeps showing up in systems engineering conversations, and
why it maps so well onto AI coding agents, which are very good at producing code and
very bad at knowing whether the code was worth producing.

## The EVO loop

An EVO project is a sequence of **steps**. A step is a small increment of delivered
value, typically one week of work, and Gilb's usual rule of thumb is that a step should
be around 1 to 2 percent of total project effort. Small steps fail cheaply and teach
quickly.

The loop for one step:

1. **Define the critical few results.** Write down the top objectives that matter to
   named stakeholders. Quantify each one.
2. **Establish the current level.** Measure where you are today. Without a baseline the
   word "improvement" has no meaning.
3. **Generate candidate steps.** List several possible things to do next, not one.
4. **Estimate the impact of each candidate.** For every objective, estimate how much of
   the remaining gap each candidate closes. Estimate cost in the same table.
5. **Choose the best value per cost.** Not the oldest item, not the loudest request,
   not the easiest ticket.
6. **Deliver the step.** Keep it small enough that delivering it is boring.
7. **Measure the result.** Use the meter defined in the requirement. Compare measured
   value and cost against the estimate.
8. **Update the model and repeat.** Some estimates were wrong. That is data, not
   failure. Re-plan the next step with the new numbers.

The chess metaphor Gilb uses fits better than it sounds. Each step is a move. A move can
advance several objectives at once. The clock is the budget. Winning means reaching all
the goal levels before the resources run out. A chess player does not plan 40 moves in
detail, but does keep a position and re-evaluates every move.

Two structural details that follow from this:

- **Steps overlap objectives.** One step can improve security and response time
  together, which is why prioritizing by single backlog items loses information.
- **Some work does not fit in one step.** Gilb's restaurant analogy: a kitchen prepares
  dishes that take longer than one serving cycle, and the dining room serves them when
  ready. Architecture work is prepared in the backroom and delivered in a later step.
  What is not allowed is delivering nothing to a stakeholder for several steps.

## Quantify first: the top ten

EVO starts with a small set of measurable objectives. Gilb calls this the **critical top
ten**, and the discipline is to keep it genuinely small. If everything is critical,
nothing is.

For each objective you need:

- **Who** benefits. A named stakeholder group, not "the user".
- **What** changes. A performance attribute, phrased as a direction.
- **How much**. Current level, target level, and the level you would be ashamed of
  falling below.
- **How you know**. A meter, meaning a measurement process, not a wish.
- **By when**. A date or a step number, because budgets include time.

A useful sanity check on the top ten:

| Question | Bad answer | Good answer |
| --- | --- | --- |
| Who is better off? | users | support agents handling refunds |
| What improves? | better UX | median refund handling time |
| How much? | faster | from 9 min to 3 min, must stay under 6 |
| How do we know? | feedback | ticket timestamps in the helpdesk export |
| By when? | soon | before the Q3 contract renewal |

Notice that the good column does not mention software features. Features are candidate
steps, not objectives. This separation is the single most useful idea to steal from EVO
even if you never run a full EVO project.

## Planguage: requirements you can measure

Planguage is Gilb's specification language, described in *Competitive Engineering*
(2005). You do not need the full language. You need about eight keywords, and they fit
on a napkin.

A scalar requirement in Planguage:

| Keyword | Meaning | Example |
| --- | --- | --- |
| **Tag** | Unique name for reuse | `RefundTime` |
| **Gist** | One line plain description | Time to process a customer refund |
| **Ambition** | Why anyone cares | Reduce support cost and customer anger |
| **Scale** | The dimension and unit | Minutes, median, business hours |
| **Meter** | How the number is produced | Helpdesk ticket timestamps, weekly export |
| **Must** | Failure level | `<= 6 min` |
| **Plan** | Committed target | `<= 3 min` |
| **Wish** | Nice to have | `<= 1.5 min` |

Written out, it reads like this:

```
Tag:        RefundTime
Gist:       Time to process a customer refund
Ambition:   Cut support cost per refund and stop refund escalations
Scale:      Minutes, median over a calendar week, business hours only
Meter:      Helpdesk export, field "refund_closed_at" minus "refund_opened_at"
Must:       <= 6.0 min
Plan:       <= 3.0 min
Wish:       <= 1.5 min
Stakeholder: Support agents, finance team, customers
Owner:      Payments team
```

Three properties matter:

1. **Ambition is not a number.** It is the reason the number matters. Gilb separates
   the political purpose from the engineering target on purpose.
2. **Must, Plan and Wish create a band.** A single target value invites gaming: you
   either hit it or you do not, and the conversation becomes binary. A band encodes
   risk appetite. If a step cannot reach Plan but stays above Must, you learned
   something and can still ship.
3. **The meter is part of the requirement.** If nobody can produce the number, the
   requirement is a slogan. This is where most teams quietly give up, and it is the
   part worth defending.

Planguage also covers functions, but briefly: functions are things the system does,
and by themselves they have no incremental value. The value comes from the quality
levels the functions enable. That claim is deliberately provocative, and it is the
philosophical core of the method.

## Impact estimation: choosing the next step

The **Impact Estimation table** is the decision tool. Rows are candidate steps, columns
are objectives plus resources. Each cell holds two numbers: the estimated percentage of
the remaining gap the step closes, and the confidence in that estimate.

A worked example. Objectives from the top ten, with current level, plan target and
weight:

- `RefundTime`: 9 min today, plan 3 min, weight 40
- `RefundError`: 6 percent of refunds need manual correction, plan 2 percent, weight 35
- `SupportCost`: 1.20 EUR per refund, plan 0.70, weight 25

| Candidate step | RefundTime | RefundError | SupportCost | Cost (dev days) | Value score | Value per cost |
| --- | --- | --- | --- | --- | --- | --- |
| A: one-click refund for small amounts | 60% | 10% | 25% | 6 | 27.5 | 4.58 |
| B: auto-fill from order history | 15% | 45% | 20% | 4 | 26.75 | 6.69 |
| C: rewrite refund service | 70% | 50% | 40% | 30 | 55.5 | 1.85 |

Value score is the weighted sum of estimated gap closure:
`0.4*60 + 0.35*10 + 0.25*25 = 24 + 3.5 + 6.25 = 33.75` for A. The table above is
simplified, but the arithmetic is the point: candidate C looks best on raw impact and is
worst on value per cost. Candidate B wins.

What makes the table useful is not precision. It is that every number is arguable in
public. An engineer can challenge the 45 percent estimate, a support lead can challenge
the weight, and the disagreement becomes specific instead of political.

Practical notes:

- Keep the table in the repository next to the code, not in a slide deck. It should
  change weekly.
- Record the estimate before delivery and the measurement after. The delta between them
  is your organization's estimation skill, and it improves fast when visible.
- Estimates above 70 percent gap closure are a smell. Big claimed jumps usually mean the
  step is really several steps wearing a coat.
- Cost includes everything you spend, including the review, the rollout, the support
  training and the cost of the risk you took.

This is also where EVO's "multiple objectives" claim becomes concrete. A step that
closes little of the top objective but a lot of a cheap secondary objective can win,
and a single-objective backlog cannot express that trade.

## The ten Evo principles

The InfoQ article lists ten principles, E1 to E10. The wording below is close to
Gilb's, with a plain gloss and a software example each.

| # | Principle | What it means in practice |
| --- | --- | --- |
| E1 | Decompose by performance results and stakeholders | Plan in slices of stakeholder value, not layers of architecture |
| E2 | Do high-risk steps early, learn how unknowns really perform | Spike the scary thing in week one, even if it delivers little value |
| E3 | Improve your most valuable performance objectives first | Work where the gap to the goal is expensive to keep |
| E4 | Base early evolution on existing systems and stakeholders | Evolve the ugly thing people use, do not rewrite first |
| E5 | Design to cost dynamically | Validate buy or build with real money before committing |
| E6 | Design to performance dynamically | Prove the quality impact of an architecture before scaling it |
| E7 | Invest in an open-ended architecture early | Keep the cost of changing your mind low |
| E8 | Motivate your team by rewarding results | Pay and praise delivery, not hours or lines of code |
| E9 | Prioritize changes by value, not place in queue | A good idea found yesterday can go first |
| E10 | Learn fast, change fast, adapt to reality fast | Short cycles, real measurements, fast reversal |

E2 deserves emphasis because it inverts normal backlog ordering. The riskiest
assumption is usually not the highest value item, so it never floats to the top of a
value-ranked backlog. EVO forces it into the first steps, because failure there is
cheap and informative. The value of a failed early step is the knowledge that the idea
does not work, bought at a discount.

E4 is the anti-rewrite principle. Gilb's claim is that evolutionary change from the
current system delivers a more revolutionary result than a revolution, because the
current system already serves real stakeholders and holds real knowledge.

E8 is the uncomfortable one. It says effort is irrelevant and completed code is not a
result. Reward the team that moved the number, not the team that was busy. Most
organizations say this and then promote the busiest person.

E9 is the argument against annual planning cycles. The committee's job is not to pick
the work, it is to approve a process that lets the project pick the best work at every
step.

## What "done" means

Gilb's definition:

> Done means no more value can be profitably delivered to stakeholders with currently
> available resources.

Everything follows from that. A sprint can be "done" while the customer is not better
off. A feature can be shipped while a stakeholder is worse off, for example because the
support desk now handles twice the tickets. Both are failures under this definition.

The corollary is that "done" is a statement about the system in its environment, not
about the code. Value depends on users, the economy, competition and politics. You can
deliver value with no code change at all, by teaching, by fixing data, by changing a
process. An EVO team is allowed to notice that.

Gilb's other jab, in the same article: velocity and burn-down measure coding, not
value. He quotes Jeff Sutherland's own claim that Scrum-only projects failed 19 percent
of the time, and asks what is still wrong. Treat that as rhetoric with a real point
underneath: measuring activity is not measuring outcomes.

## Architecture and technical debt are requirements

E7 is the principle most relevant to modern software work, and the most often skipped.

The argument: you will have architecture disappointments. If each disappointment is
expensive to reverse, you will defend bad decisions instead of replacing them. So
changeability has to be engineered in early, and it should be a quantified requirement
like any other.

Concretely:

- **Cycle time of a change** is a meter. Median time from merged requirement to
  production, measured, with a Must and a Plan.
- **Cost of a small change** is a meter. Developer days for a representative change,
  measured every quarter on the same benchmark task.
- **Blast radius** is a meter. Number of services or modules touched by a typical
  change.
- **Onboarding time** is a meter. Days until a new developer ships a change to
  production.

Gilb's Confirmit case study, the "Green Week", is the worked example: technical debt
reduced by engineering it as a quality objective with numbers, not by declaring a
cleanup sprint. The deeper point is that "reduce technical debt" is not measurable and
therefore not actionable. "Reduce median change cycle time from 11 days to 4" is.

Modern framing: developer experience metrics and DORA metrics are the same idea with
better dashboards. EVO got there first and demanded a target level, which is the part
most dashboards still lack.

## EVO compared with Scrum, XP and waterfall

No method is universally better. The differences below are the ones that change
behavior.

| Dimension | EVO | Scrum | XP | Waterfall |
| --- | --- | --- | --- | --- |
| Unit of delivery | Value step, typically weekly | Sprint increment | Small release, continuous | Phase gate |
| Planning horizon | One step, re-prioritized every step | Sprint, fixed once started | Days to weeks | Whole project |
| Requirement form | Quantified scalar with scale and meter | User story plus acceptance criteria | Story plus test | Specification document |
| Definition of done | Value level reached, measured | Increment meets the team's DoD | Tests pass, integrated | Phase signed off |
| Progress metric | Movement on quantified objectives | Velocity, burn-down | Test count, integrated builds | Percent complete |
| Risk handling | High-risk steps first, by design | Risks in backlog, often late | Spike, test-first | Risk register, analysis |
| Priority changes | Any step boundary, by value per cost | Next sprint | Continuous | Change control board |
| Reward basis | Delivered results | Team velocity, sometimes | Working software | Milestone hit |
| Strongest at | Multi-objective trade-offs, quality goals | Team rhythm, visibility | Engineering discipline | Fixed scope contracts |
| Weakest at | Measurement overhead, skill requirement | Outcome measurement | Stakeholder value framing | Change |

Some honest comparisons:

- **Against Scrum.** Scrum is a container. It does not say what a good requirement is,
  and it does not require measuring outcomes. A team can run perfect Scrum for a year
  and never move a stakeholder number. EVO is a content discipline, and it can live
  inside Scrum if you want the ceremonies.
- **Against XP.** XP contributes the engineering practices that make small steps
  affordable: test-first, continuous integration, refactoring. EVO without those
  practices is a measurement religion with a slow feedback loop. The two combine well.
- **Against waterfall.** EVO shares waterfall's appetite for early specification and
  differs on everything else: specification is numeric, planning is one step deep, and
  the plan changes when reality disagrees.
- **Against Kanban.** Kanban optimizes flow and limits work in progress. EVO asks which
  item deserves the slot. Flow without value ranking moves the wrong things faster.

## Common misreadings

**"EVO means big up-front requirements."** No. It means quantified objectives early,
and those objectives are allowed to change. The specification that is expensive to
change is the solution, not the target.

**"EVO is waterfall with measurement."** No. The loop is one step long, and the
measurement changes the plan. Waterfall measures progress against a plan made before
learning anything.

**"Planguage is documentation overhead."** You can write a scalar in six lines and keep
it next to the code. The overhead is the meter, and the meter is the point.

**"We already do this, we have KPIs."** KPIs are usually lagging business numbers
reported quarterly, disconnected from the work. EVO requires the number to be
attributable to steps and available at step frequency.

**"EVO only works for huge projects."** Gilb's cases include small projects. But the
measurement overhead is real, and below a certain size it is not worth it. See the next
section.

## When EVO is hard

Being honest about limits makes the rest credible.

1. **Measurement is a project of its own.** Instrumentation, data access and a data
   owner cost real effort before the first step ships. Teams routinely underestimate
   this by an order of magnitude.
2. **Stakeholders must be reachable.** EVO needs people who can say what value means
   and who will look at the number every week. If the customer is a procurement
   department three time zones away, the loop stalls.
3. **Quantification is a skill.** Bad scales produce fake precision, and fake precision
   is worse than none because people trust it. "Quality score 0 to 10" is not a scale.
4. **Politics.** Numbers are arguments. Publishing them makes some arguments
   unwinnable, and not everyone wants that.
5. **Small projects.** Two people, two weeks, one stakeholder: just ship and ask.
   The ceremony is not free.
6. **The rhetoric.** Gilb is dismissive of much agile practice, and the tone puts
   readers off. Separate the method from the polemic.
7. **Evidence base.** Most EVO literature is practitioner reporting and case studies,
   not controlled studies. The method is coherent and the cases are real, but treat
   strong claims about superiority as claims.
8. **Gaming.** Any published target invites optimization of the number rather than the
   outcome. Gilb's own answer is multiple objectives and multiple stakeholders, which
   raises the cost of gaming, but does not eliminate it.

## Introducing EVO without a revolution

You do not need permission to run an EVO project. You need one page and one habit.

A workable adoption path, in order:

1. **Write the top five, not ten.** Five quantified objectives, each with a scale, a
   meter, a current level and a plan level. If you cannot produce a current level, the
   first step is to measure it.
2. **Publish the baseline.** Include the embarrassing numbers. This is the step most
   teams skip and it is the one that creates trust.
3. **Add one column to your existing board.** "Which objective does this move, and by
   how much?" Items with no answer do not get prioritized, they get questioned.
4. **Estimate before, measure after, on one step.** Pick the next piece of work, write
   the estimate, ship it, measure. Show the delta.
5. **Keep the table in the repo.** `value/impact-estimation.md` with a date on every
   row. Review it in the same meeting where you plan.
6. **Add a changeability objective.** Median cycle time or cost of a representative
   change. Watch how quickly it becomes the most useful number you have.
7. **Only then formalise.** If the habit sticks for a quarter, the rest of EVO is
   mostly vocabulary.

## Try it this week

A checklist you can finish in five days without buying anything.

- [ ] List five stakeholder groups. Pick the one that is most expensive to ignore.
- [ ] Write three results that group cares about, in the direction of improvement.
- [ ] For each, write scale, meter, current level, Must, Plan. Steal the Planguage
      template above.
- [ ] Measure the current level. If the meter does not exist, that is your first step.
- [ ] List five candidate steps for the next two weeks.
- [ ] Estimate impact and cost in one table. Pick the best value per cost.
- [ ] Deliver the smallest one. Measure. Write down the estimate versus the result.
- [ ] Repeat with the numbers you now have.

If only one habit survives, make it this: every piece of work must name the stakeholder
number it moves. That alone changes more conversations than a full method rollout.

## Glossary

- **EVO**: Evolutionary Value Delivery, Gilb's method.
- **Step**: one small delivery of value, typically a week, ideally around 2 percent of
  project effort.
- **Top ten**: the critical few quantified objectives.
- **Planguage**: Gilb's specification language for requirements, designs and results.
- **Scalar**: one quantified requirement with a scale and a meter.
- **Scale**: the dimension and unit of measurement.
- **Meter**: the process that produces the number.
- **Must, Plan, Wish**: failure level, committed target, stretch target.
- **Impact Estimation table**: candidate steps scored against objectives and resources.
- **Value**: perceived benefit to a defined stakeholder under defined conditions.
- **Backroom**: work prepared ahead of the step that delivers it.

## References

Primary sources:

- Tom Gilb and Kai Gilb, "Evo: The Agile Value Delivery Process, Where Done Means Real
  Value Delivered", InfoQ, January 2015.
  https://www.infoq.com/articles/evo-agile-value-delivery/
- Tom Gilb, "Fundamental Principles of Evolutionary Project Management", ICEIS 2004
  keynote.
  https://iceis.scitevents.org/ICEIS2004/keynote_lectures/Gilb%20KL.pdf
- Tom Gilb, *Competitive Engineering: A Handbook for Systems Engineering, Requirements
  Engineering, and Software Engineering Using Planguage*, Elsevier, 2005.
- Craig Larman, "Chapter 10: Evolutionary Project Management and Planguage", in *Agile
  and Iterative Development*.
  https://www.craiglarman.com/wiki/downloads/agile_iterative/larman-ch10-agile-1e-evo-and-planguage.pdf
- Tom Gilb, "10 Evolutionary Project Management Principles", PMHut series, 2008.
  https://pmhut.com/10-evolutionary-project-management-principles-evo-principle-2
- Tom Gilb, "How to Quantify Quality: Finding Scales of Measure", Methods and Tools.
  https://www.methodsandtools.com/archive/archive.php?id=91

Talks and case material:

- Tom Gilb, "Evo: The Most Advanced Agile Process", AgileByExample 2017.
  https://www.youtube.com/watch?v=f0In1hDKjkw
- Tom Gilb, "Evo and Agile: Deliver value with real Agile".
  https://www.youtube.com/watch?v=_Nh6281xpoc
- Tom Gilb, "The Green Week: Reducing Technical Debt by Engineering", Confirmit case
  study, 2013.
  http://www.gilb.com/dl575
- Evolutionary Delivery, C2 wiki.
  https://wiki.c2.com/?EvolutionaryDelivery
- "Evolutionary Project Management Tool (EVO)", Agilia Conference 2013 workshop.
  https://agiliaconference.com/2013/en/workshops/evolutionary-project-management-tool-evo.html

Background:

- Evolutionary development, ResearchGate overview.
  https://www.researchgate.net/publication/234783638_Evolutionary_development
- Tom Gilb, "How well does the Agile Manifesto align with principles that lead to
  success in product development".
  https://www.gilb.com/blog/how-well-does-the-agile-manifesto-align-with-principles-that-lead-to-success-in-product-development

Continue with [EVO in the AI harness era](evo-in-ai-era.md), which takes these
principles and maps them onto coding agents, token budgets and long-running
autonomous work.
