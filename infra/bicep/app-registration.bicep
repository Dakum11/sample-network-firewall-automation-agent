param crpName string = 'firewall-automation-chatbot'
param ciNumber string = 'your-ci-number-here'
param sraNumber string = '1326982'

resource CustomApplicationRP 'Microsoft.CustomProviders/resourceproviders/Application@2018-09-01-preview' = {
  name: 'CustomApplicationRP/Application'
  location: 'global'
  properties: {
    applicationRegistrationName: '${crpName}'
    applicationRegistrationCI: '${ciNumber}'
    applicationRegistrationSRANumber: '${sraNumber}'
    permissions: ['email', 'profile', 'openid', 'User.Read']
    owners: ['admin@example.com']
  }
  dependsOn: []
}
