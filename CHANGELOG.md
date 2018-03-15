## 0.4.1
* Changed setup config for PyPI

## 0.4.0
* Add Django 2.0 support #23
* Drop support for Django 1.8

## 0.3.3
* Fix multipart form data (@ron8mcr)

## 0.3.2
* Support relation fields that do not have `related_name` specified #24 (@jpnauta)

## 0.3.1
* Fix problem with different field name specified via `source` attribute #22

## 0.3.0
* Fix problem with deletion related M2M objects when removing the relation
(Note: you should manually delete m2m instances on update after this version)

## 0.2.1
* Fix problem for updating models with UUID primary key field (@kseniyashaydurova)
* Fix problem with raising Protected Error in deletion (@kseniyashaydurova)

## 0.2.0
* Add support for custom primary key field #10 (@tjwalch)
* Add possibility to pass through argument from serializer.save method (@tjwalch)
* Add possibility to update direct relations on create (@tjwalch)

## 0.1.4
* Add support for GenericRelation (@tjwalch)

## 0.1.3
* Handle when serializer has a field that's not on the model #5 (@tjwalch)

## 0.1.2
* Fix problem with null values for reverse relations

## 0.1.0
* Remove unneeded functional
* Cover with tests

## 0.0.1
* Initial public release
