## 0.5.4
* Update UniqueFieldsMixin to support DRF 3.11 validator context API (@mands)

## 0.5.3
* Support custom resource_type_field_name for polymorphic serialize (@tsaipoan)

## 0.5.2
* Feature: Enable support for nested polymorphic relations #81 (@csdenboer)

## 0.5.1
* Fix: Validate nested field before creating it even in partial update (@yuekui) 
* Fix some potential issues  in the delete phase for reverse relations update

## 0.5.0
* Workaround: Validation problem: `parent` isn't set for nested serializer's fields on the validation stage #1 (@kenny1992)
* Fix: Validation problem: custom validation errors raised from the nested serializer have a wrong path #2 (@kenny1992)

## 0.4.3
* Fix MultiValueDictKeyError for nested updates on reverse-relations  (@bakerf @projkov)

## 0.4.2
* Allow child one-to-one instances to be updated without providing PK (@karamanolev @cjroth @mathieuseguin)

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
