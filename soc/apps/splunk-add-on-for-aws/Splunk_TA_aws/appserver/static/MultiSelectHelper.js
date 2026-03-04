/*
 * SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
 * SPDX-License-Identifier: LicenseRef-Splunk-8-2021
 *
 */

require([
  'underscore',
  'splunkjs/mvc',
  'splunkjs/mvc/multiselectview',
  'splunkjs/mvc/multidropdownview',
  'splunkjs/mvc/tokenforwarder',
  'splunkjs/mvc/simplexml/ready!'
], function (_, mvc, MultiSelectView, MultiDropdownView, TokenForwarder) {
  'use strict'

  const multiSelectVal = function () {
    let newValue = arguments[0]
    const choices = this.settings.attributes.choices
    let allValue = '*'

    // This is for All value which is not '*', could have performance issue for
    // too many dropdown options.
    if (choices.length > 1 && choices[0].value !== '*') {
      allValue = _.map(choices.slice(1), function (choice) {
        return choice.value
      }).join(' OR ')
    }

    if (_.isArray(newValue) && newValue.length > 1) {
      const allPos = newValue.indexOf(allValue)

      if (allPos !== -1) {
        if (allPos === 0) {
          newValue = _.without(newValue, allValue)
        } else if (allPos === newValue.length - 1) {
          newValue = [allValue]
        }
      }

      arguments[0] = newValue
    }
    return MultiDropdownView.prototype.val.apply(this, arguments)
  }

  Object.keys(mvc.Components.attributes).forEach(function (componentName) {
    const component = mvc.Components.get(componentName)
    if (component instanceof MultiSelectView) {
      component.val = multiSelectVal
    }
  })

  function forwardFunc (sourceToken) {
    if (sourceToken && !(sourceToken instanceof Array) && sourceToken.indexOf(',') !== -1) {
      // if multiple choices are selected, form.token is transformed into
      // a string delimited by comma
      return sourceToken.split(',')
    }
    return sourceToken
  }
  /* eslint-disable no-new */
  new TokenForwarder(['$form.datainput$'], '$form.datainput$', forwardFunc)
  new TokenForwarder(['$form.host$'], '$form.host$', forwardFunc)
  new TokenForwarder(['$form.modinput$'], '$form.modinput$', forwardFunc)
})
