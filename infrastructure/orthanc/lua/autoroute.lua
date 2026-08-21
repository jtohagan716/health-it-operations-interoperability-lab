function OnStoredInstance(instanceId, tags, metadata, origin)

    local accession = tags['AccessionNumber']

    if accession == 'RADROUTE001' then

        print(
            'AUTO-ROUTE MATCH: ' ..
            'instance=' .. instanceId ..
            ' accession=' .. accession ..
            ' destination=interoplab'
        )

        SendToModality(
            instanceId,
            'interoplab'
        )

        print(
            'AUTO-ROUTE COMPLETE: ' ..
            'instance=' .. instanceId
        )

    else

        print(
            'AUTO-ROUTE SKIP: ' ..
            'instance=' .. instanceId ..
            ' accession=' ..
            tostring(accession)
        )

    end
end