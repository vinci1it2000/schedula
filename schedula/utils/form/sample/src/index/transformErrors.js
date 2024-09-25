/*
 * # -*- coding: utf-8 -*-
 * #
 * # Copyright 2024 sinapsi - s.r.l.;
 * # Licensed under the EUPL (the 'Licence');
 * # You may not use this work except in compliance with the Licence.
 * # You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
 *
 */

export default function transformErrors(errors, uiSchema) {
    return errors.filter(error => !['if'].includes(error.name))
}