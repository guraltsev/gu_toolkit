
# Weak idempotency of `SmartFigure.parameter`
Calls to SmartFigure.parameter should be weakly idempotent in the following sense:


The parameter call looks like this 
```python
parameter(a, min=1, max=2, step=0.001, value=1)
```
OR it may lack some of the named arguments `(min, max, step, value)`

IF parameter `a` DOES NOT exist then the missing values should be filled in with the default (min=-1,max=1, step=0.01, value=0) and the parameter should be created. 

IF the parameter `a` DOES exist, then ONLY the specified values should be updated. For example

```python
parameter(a, min=1, max=2, step=0.001)
```
should NOT update the default value. 


# Access through `params`

Parameter access through `SmartFigure.params` behaves slightly differently:

`SmartFigure.params[a].value=1` 
updates the value but not the default value
`SmartFigure.params[a].default_value=1` 
updates the default value but does NOT change the current value.
min/max/step behave as expected. 


# Discoverability
Design and implement a way for which exposed options in `SmartFigure.params[a]` can be discoverable. When I tried, I was not able to figure out that min, max, step were acceptable values. 