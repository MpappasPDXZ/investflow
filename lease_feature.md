@README.md - okay, let's start.  please review this document for how this system works.  I want to ensure we are using hot refresh.  
structured data storage:
I want you to review the structured data stored in this workflow FastAPI --> Lakekeeper --> Postgresql --> iceberg in ADLS.  
unstructured data storage:
We store all documents both for testing and in production in ADLS.  All metadata about the documents is in the vault feature.
I test locally the front end and prefer one hot reloading over full container rebuilds.  However, full container rebuilds and restarts are necessary in a lot of cases to fix the code.
I want to make my styling (buttons, font sizes, compactness) to mirror the properties page.
|----------------------|
|-- Lease generation --|
|----------------------|

overall layout:
|-----------------------------|
| lease parameter table       |
|-----------------------------|
|-----------||----------------|
|lease      ||generated lease |
|parameters ||                |
|single set ||                | 
|           ||                | 
|           ||                |
|           ||                |
------------------------------|
I want to ensure I have all the correct lease parameters stored.  
Here's the workflow:
1-user clicks on left hand shadcn menu: leases (take create lease and view lease down to one button).  (Shad CN menu is left of lease parameters all the time)
2-opens up a table where the user can add or edit lease parameters (lease parameter table).
3-user clicks a set of parameters (should be one button for edit or view) and it collapses the top header div which is for the parameter table.  Now we're viewing an iceberg table of lease parameters (lease parameters table)
4-user now has a left hand div with a single lease parameter set to fill in.  and a right hand div which is the lease document.  the save button for the left hand div lease parameters should be at the bottom of the lease parameters div.  Make sure the left hand div is 50% of the width of the screen and the lease itself (generated lease) has the capability to fully expand.  When working on the lease parameters we want the header collapsed because the lease parameters are numerous.  The save parameters and save & generate PDF buttons need to be in the lease parameters (single lease parameter) div.

5-When the user saves parameters make sure we can trace what data has been posted.  We have major issues right now where the data is not saving.  We are going to make 10-15 adjustments on the lease parameters and we need for the AI to understand exactly how to add new, upsert, delete the iceberg table values, and have it go into the [lease parameter table].  

6-Once the lease parameters single set save occurs we store the values first. Then we generate a new document.  

7-Now we're going to review the lease document (generated lease) and ensure the legal language is correct.  This is going to produce a "do-loop" where I alter the parameters 10-15 times to get the generated lease correct.